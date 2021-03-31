#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from os import getenv
from logging import getLogger
from typing import Union
from datetime import date, datetime
from json import dumps
from hashlib import blake2b

# 3rd party:
from starlette.datastructures import URL

# Internal:
from app.exceptions import InvalidQuery, BadRequest
from .. import constants as const
from ..assets import RequestMethod, MetricData
from ..formatters import json_formatter

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'Request'
]


logger = getLogger('COVID19-APIv2')

ENVIRONMENT = getenv("API_ENV", "PRODUCTION")


class Request:
    area_type: str
    release: date
    format: str
    metric: list[str]
    area_code: str
    method: str
    url: URL

    _path: str
    _partition_id: str
    _db_args: list[Union[str, list[str]]]
    _db_metrics: set[str]
    _nested_metrics: list[str]
    _db_query: str

    def __init__(self, area_type: str, release: str, format: str, metric: list[str],
                 area_code: str, method: str, url: URL):
        self.area_type = area_type
        self.release = datetime.strptime(release[:10], "%Y-%m-%d").date()
        self.format = format
        self.area_code = area_code
        self.method = method
        self.url = url

        if len(metric) and ',' in metric[0]:
            self.metric = metric[0].split(',')

        logger.info(dumps({"requestURL": str(url)}))

    @property
    def path(self) -> str:
        if (path := getattr(self, '_path', None)) is not None:
            return path

        filename = blake2b(
            str.join("&", self.metric).encode(),
            digest_size=5,
            key=f"{self.release:%Y%m%d}".encode()
        ).hexdigest()

        path = f"{self.release}/{self.area_type}"
        if self.area_code is not None:
            path = f"{path}/{self.area_code}"
        else:
            path = f"{path}/complete"
        path = f"{path}/{filename}.{self.format}"

        self._path = path

        logger.info(dumps({"cachePath": self._path}))

        return self._path

    @property
    def metric_tag(self) -> dict[str, str]:
        metrics = str.join(":", self.metric)
        return {"metrics": metrics}

    @property
    def partition_id(self) -> str:
        if (partition_id := getattr(self, '_partition_id', None)) is not None:
            return partition_id

        area_type = self.area_type.lower()

        if self.area_type not in MetricData.single_partition_types:
            area_type = "other"  # Default DB partition suffix.

        self._partition_id = f"{self.release:%Y_%-m_%-d}_{area_type}"

        logger.info(dumps({"partitionId": self._partition_id}))

        return self._partition_id

    @property
    def db_args(self) -> list[Union[str, list[str]]]:
        if (db_args := getattr(self, '_db_args', None)) is not None:
            return db_args

        db_args = [list(self.db_metrics), self.area_type]

        if self.area_code is not None:
            db_args.append(self.area_code)

        self._db_args = db_args

        logger.info(dumps({"arguments": self._db_args}, default=json_formatter))

        return self._db_args

    @property
    def db_metrics(self) -> set[str]:
        if (db_metrics := getattr(self, '_db_metrics', None)) is not None:
            return db_metrics

        self._db_metrics = set(self.metric) - {"areaCode", "areaName", "areaType", "date"}

        logger.info(dumps({"metrics": list(self._db_metrics)}))

        return self._db_metrics

    @property
    def nested_metrics(self) -> list[str]:
        if (nested_metrics := getattr(self, '_nested_metrics', None)) is not None:
            return nested_metrics

        self._nested_metrics = list(set(self.metric).intersection(MetricData.json_dtypes))

        logger.info(dumps({"nestedMetrics": self._nested_metrics}))

        return self._nested_metrics

    @property
    def db_query(self) -> str:
        if (db_query := getattr(self, '_db_query', None)) is not None:
            return db_query

        filters = str()

        if ENVIRONMENT != "DEVELOPMENT":
            # Released metrics only.
            filters += " AND mr.released IS TRUE\n"

        if self.area_code is not None and self.area_type != "msoa":
            filters += f" AND ar.area_code = $3"

        if self.method == RequestMethod.Get:
            if self.nested_metrics and len(self.nested_metrics) == len(self.metric) == 1:
                # Processing nested metric: only one metric is allowed per
                # request when a nested metric name is present in `self.metric`.
                query = const.DBQueries.nested_array
                query = query.substitute(
                    partition=self.partition_id,
                    filters=filters,
                    metric_name=self.nested_metrics[0]
                )
            elif self.nested_metrics and len(self.metric) > 1:
                # When a nested metric is present in `self.metric` and
                # `self.metric` has more than one metric, the request
                # is declined:
                nested_metrics = set(self.nested_metrics)
                raise InvalidQuery(
                    details=(
                        f"Nested metrics - e.g. {nested_metrics} - cannot be requested "
                        f"alongside other metrics. "
                        f"Remove {set(self.metric) - nested_metrics} and try again."
                    )
                )
            else:
                # When no nested metric is present in `self.metric`:
                # print(self.area_type)
                if self.area_type != "msoa":
                    query = const.DBQueries.main_data
                elif self.area_type == "msoa" and self.area_code is None:
                    query = const.DBQueries.nested_object
                else:
                    query = const.DBQueries.nested_object_with_area_code

                query = query.substitute(partition=self.partition_id, filters=filters)

        elif self.method == RequestMethod.Head:
            query = const.DBQueries.exists
            query = query.substitute(partition=self.partition_id, filters=filters)

        else:
            raise BadRequest()

        logger.info(dumps({"query": query}))

        self._db_query = query

        return self._db_query
