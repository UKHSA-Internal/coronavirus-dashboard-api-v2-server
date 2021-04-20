#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from datetime import datetime
from os import getenv
from dataclasses import dataclass
from typing import Dict

# 3rd party:

# Internal:
from app.database import Connection
from app.config import Settings
from . import constants as const

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'get_latest_timestamp',
    'RequestMethod',
    'MetricData',
    'add_cloud_role_name'
]


ENVIRONMENT = getenv("API_ENV", "PRODUCTION")

TYPE_MAP: Dict[object, object] = {
    int: float,
    float: float,
    str: str
}

data_types = const.DATA_TYPES.copy()
data_types["date"] = str


query = """\
SELECT rr.timestamp 
FROM covid19.release_reference AS rr
JOIN covid19.release_category AS rc ON rc.release_id = rr.id
WHERE DATE(rr.timestamp) = $1
  AND rc.process_name = $2\
"""

if ENVIRONMENT != "DEVELOPMENT":
    query += " AND rr.released IS TRUE"


async def get_latest_timestamp(request) -> datetime:
    area_type = request.area_type.lower()

    if area_type == "msoa":
        category = "MSOA"
    else:
        category = "MAIN"

    async with Connection() as conn:
        timestamp = await conn.fetchval(query, request.release, category)

    return timestamp


@dataclass()
class RequestMethod:
    Get: str = "GET"
    Head: str = "HEAD"
    Options: str = "OPTIONS"
    Post: str = "POST"
    Put: str = "PUT"
    Patch: str = "PATCH"


@dataclass()
class MetricData:
    base_metrics = ["areaType", "areaCode", "areaName", "date"]

    dtypes = data_types

    generic_dtypes = {
        metric_name: TYPE_MAP.get(data_types[metric_name], object)
        if data_types[metric_name] not in [int, float] else float
        for metric_name in data_types
    }
    integer_dtypes = {type_ for type_, base_type in data_types.items() if base_type is int}
    string_dtypes = {type_ for type_, base_type in data_types.items() if base_type is str}
    json_dtypes = {type_ for type_, base_type in data_types.items() if base_type in [list, dict]}

    # Non-default DB partition suffixes (area types in lower case).
    single_partition_types = {"utla", "ltla", "nhstrust", "msoa"}

    nested_struct = {
        "newCasesBySpecimenDateAgeDemographics": ["age", "cases", "rollingSum", "rollingRate"],
        "newCasesByPublishDateAgeDemographics": ["age", "cases", "rollingSum", "rollingRate"],
        "newDeaths28DaysByDeathDateAgeDemographics": ["age", "deaths", "rollingSum", "rollingRate"],
        "cumAdmissionsByAge": ["age", "rate", "value"],
        "maleCases": ["age", "rate", "value"],
        "femaleCases": ["age", "rate", "value"]
    }


def add_cloud_role_name(envelope):
    envelope.tags['ai.cloud.role'] = Settings.cloud_role_name
    return True
