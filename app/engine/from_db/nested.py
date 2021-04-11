#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import Iterable

# 3rd party:
from asyncpg import Record
from pandas import DataFrame, json_normalize

# Internal:
from app.utils.operations import Request
from app.utils.assets import MetricData

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def process_nested_data(results: Iterable[Record], request: Request) -> DataFrame:
    nested_metric_name = request.nested_metrics[0]
    base_columns = [
        "areaCode", "areaType", "areaName", "date", "metric",
    ]

    if request.format == "csv":
        df = json_normalize(
            map(dict, results),
            nested_metric_name,
            [*base_columns, MetricData.nested_struct[nested_metric_name]],
            errors='ignore'
        )

        df.rename(
            columns={col: col.removeprefix(f"{nested_metric_name}.") for col in df.columns},
            inplace=True
        )

        columns = [*base_columns, *MetricData.nested_struct[nested_metric_name]]
    else:
        df = DataFrame(
            results,
            columns=["areaCode", "areaType", "areaName", "date", "metric", nested_metric_name]
        )
        columns = df.columns

    payload = (
        df
        .sort_values(["date", "areaCode"], ascending=[False, True])
        .loc[:, columns]
    )
    payload = payload.where(payload.notnull(), None)

    return payload
