#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import Iterable

# 3rd party:
from pandas import DataFrame
from asyncpg import Record

# Internal:
from app.utils.operations import Request
from app.utils.assets import MetricData
from .utils import format_dtypes, format_data
from .msoa import format_msoas

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'process_generic_data'
]


def process_generic_data(results: Iterable[Record], request: Request) -> DataFrame:
    df = DataFrame(results, columns=[*MetricData.base_metrics, "metric", "value"])

    response_metrics = df.metric.unique()
    column_types = {
        metric: MetricData.generic_dtypes[metric]
        for metric in filter(response_metrics.__contains__, MetricData.generic_dtypes)
    }

    try:
        payload = (
            df
            .pivot_table(
                values="value",
                index=MetricData.base_metrics,
                columns="metric",
                aggfunc='first'
            )
            .reset_index()
            .sort_values(["date", "areaCode"], ascending=[False, True])
            .pipe(format_dtypes, column_types=column_types)
            .loc[:, [*MetricData.base_metrics, *response_metrics]]
            .pipe(format_msoas, request=request)
            .pipe(format_data, response_metrics=response_metrics)
        )
    except KeyError as err:
        # This can happen if there are only null values in the df
        # then some operations on the dataframe can't be performed
        # Return the expected Dataframe object
        payload = DataFrame()

    return payload
