#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:

# 3rd party:
from pandas import DataFrame, read_csv

# Internal:
from app.utils.constants import BASE_DIR
from app.utils.operations import Request

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_msoas'
]


MSOA_RELATIONS_PATH = BASE_DIR.joinpath("static", "msoa_relations.csv")


def format_msoas(df: DataFrame, request: Request) -> DataFrame:
    if request.area_type == "msoa":
        init_cols = df.columns
        msoa_relations = read_csv(MSOA_RELATIONS_PATH, index_col=["areaCode"])

        df = (
            df
            .join(msoa_relations, on=["areaCode"])
            .loc[:, [*msoa_relations.columns, *init_cols]]
        )

    return df
