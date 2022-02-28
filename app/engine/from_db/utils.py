#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import Dict, Iterable
from tempfile import NamedTemporaryFile
from asyncio import Lock

# 3rd party:
from pandas import DataFrame
from orjson import dumps, loads

# Internal:
from app.exceptions import NotAvailable
from app.storage import AsyncStorageClient
from app.utils.operations import Request
from app.utils.assets import MetricData

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_dtypes',
    'format_data',
    'format_response',
    'cache_response'
]


async def cache_response(func, *, request: Request, **kwargs) -> bool:
    kws = {
        "container": "apiv2cache",
        "path": request.path,
        "compressed": False,
        "cache_control": "max-age=90, s-maxage=300",
        "content_type": request.content_type,
        "content_disposition":
            f'attachment; filename="{request.area_type}_{request.release:%Y-%m-%d}.'
            f'{request.format if request.format != "xml" else "json"}"',

    }

    prefix, suffix, delimiter = b"", b"", b""

    if request.format in ['json', 'xml']:
        prefix, suffix, delimiter = b'{"body":[', b']}', b','

    current_location = 0

    async with AsyncStorageClient(**kws) as blob_client:
        try:
            # Create an empty blob
            await blob_client.upload(b"")
            await blob_client.set_metadata({"done": "0", "in_progress": "1"})

            with NamedTemporaryFile() as fp:
                async with blob_client.lock_file(60) as blob_lock:
                    async for index, item in func(request=request, **kwargs):
                        async with Lock():
                            if not (index and current_location):
                                fp.write(prefix)
                                fp.write(item)

                            elif not index and current_location:
                                fp.seek(0)
                                tmp = item + fp.read()
                                fp.seek(0)
                                fp.truncate(0)
                                fp.write(tmp)

                            elif item:
                                fp.write(delimiter)
                                fp.write(item)

                            current_location = fp.tell()

                        # Renew the lease by after each
                        # iteration as some processes may
                        # take longer.
                        await blob_lock.renew()

                    async with Lock():
                        fp.write(suffix)
                        fp.seek(0)

                        # Anything below 40 bytes won't contain any
                        # data and won't be cached.
                        if fp.tell() == 40:
                            raise NotAvailable()

                        await blob_client.upload(fp.read())

                    tags = request.metric_tag
                    tags["done"] = "1"
                    tags["in_progress"] = "0"
                    await blob_client.set_metadata(tags)

        except Exception as err:
            # Remove the blob on exception - data may be incomplete.
            if await blob_client.exists():
                await blob_client.delete()
            raise err

    # return responder
    return True


def format_dtypes(df: DataFrame, column_types: Dict[str, object]) -> DataFrame:
    json_columns = MetricData.json_dtypes.intersection(column_types)

    # Replace `null` string with None. This happens because
    # some DB queries convert `null` to `"null"` for type
    # consistency.
    df = df.replace('null', None)
    df.loc[:, json_columns] = (
        df
        .loc[:, json_columns]
        .apply(lambda column: column.map(loads))
    )

    return df.astype(column_types)


def format_data(df: DataFrame, response_metrics: Iterable[str]) -> DataFrame:
    int_response_metrics = list(set(response_metrics).intersection(MetricData.integer_dtypes))
    df.loc[:, int_response_metrics] = df.loc[:, int_response_metrics].astype(object)

    # Pandas only supports `float` type for columns with `NaN`.
    # Convert non-null values int cells to `int`, so that they
    # won't be exported with a training `.0` in the response.
    for col in int_response_metrics:
        notnull = df[col].notnull()
        df.loc[notnull, col] = df.loc[notnull, col].astype(int)

    # Replace `NaN` with `None`. The former is exported as `NaN`
    # in JSON/CSV and is invalid. The latter is exported as `null`
    # in JSON and an empty field in CSV.
    df = df.where(df.notnull(), None)

    str_response_metrics = list(
        set(response_metrics)
        .intersection(MetricData.string_dtypes)
    )

    df.loc[:, str_response_metrics] = (
        df
        .loc[:, str_response_metrics]
        .apply(lambda column: column.str.strip('"'))
    )

    return df


def format_response(df: DataFrame, response_type: str, request: Request,
                    include_header: bool = True) -> bytes:
    if response_type == 'csv':
        base_metrics = ["areaCode", "areaName", "areaType", "date"]

        if request.area_type == "msoa":
            base_metrics = [
                "regionCode", "regionName", "UtlaCode", "UtlaName", "LtlaCode", "LtlaName",
                *base_metrics
            ]

        if not len(request.nested_metrics):
            request_metrics = sorted(request.db_metrics)
            metrics = [*base_metrics, *request_metrics]
        else:
            nested_metric = request.nested_metrics[0]
            metrics = [*base_metrics, *MetricData.nested_struct[nested_metric]]

        for metric in set(metrics) - set(df.columns):
            df = df.assign(**{metric: None})

        csv_response = (
            df
            .loc[:, metrics]
            .to_csv(
                float_format="%.1f",
                date_format="iso",
                index=False,
                header=include_header
            )
        )
        return csv_response.encode()

    df_dict = df.to_dict(orient='records')

    if response_type == 'jsonl':
        df_jsonl_gen: list[bytes] = list(map(dumps, df_dict))
        return bytes.join(b"\n", df_jsonl_gen) + b"\n"

    json_response = dumps(df_dict)

    # Remove brackets: for JSON response, leading and
    # trailing brackets must be added later as a part
    # of the streaming process.
    return json_response[1:-1]
