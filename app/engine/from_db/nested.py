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
            base_columns,
        )
    else:
        df = DataFrame(
            results,
            columns=["areaCode", "areaType", "areaName", "date", "metric", nested_metric_name]
        )

    payload = (
        df
        .sort_values(["date", "areaCode"], ascending=[False, True])
    )
    payload = payload.where(payload.notnull(), None)

    return payload
