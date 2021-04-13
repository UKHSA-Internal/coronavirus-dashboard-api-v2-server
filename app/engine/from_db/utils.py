#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import Dict, Iterable
from functools import wraps
from tempfile import NamedTemporaryFile

# 3rd party:
from pandas import DataFrame
from orjson import dumps, loads

# Internal:
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


def cache_response(func):
    """
    Storage cache decorator.
    """
    @wraps(func)
    async def responder(*, request: Request, cache_results: bool, **kwargs):
        data = func(request=request, cache_results=cache_results, **kwargs)
        if not cache_results:
            async for item in data:
                yield item

            return

        async with AsyncStorageClient("apiv2cache", request.path) as blob_client:
            try:
                # Create an empty blob
                await blob_client.upload(b"")

                with NamedTemporaryFile() as fp:
                    async with blob_client.lock_file(15) as lock:
                        async for item in data:
                            fp.write(item)

                            yield item

                            # Renew the lease by after each
                            # iteration as some processes may
                            # take longer.
                            await lock.renew()

                        fp.seek(0)
                        await blob_client.upload(fp.read())

                await blob_client.set_tags(request.metric_tag)

            except Exception as err:
                # Remove the blob on exception - data may be incomplete.
                if await blob_client.exists():
                    await blob_client.delete()
                raise err

    return responder


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
