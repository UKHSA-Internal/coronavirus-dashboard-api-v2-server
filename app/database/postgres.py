#!/usr/bin python3

"""
<Description of the programme>

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       10 Mar 2021
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import Any
from logging import getLogger
from os import getenv

# 3rd party:
from asyncpg import connect, Connection as PGConnection
from orjson import loads, dumps
from asyncpg.exceptions import PostgresLogMessage
# Internal: 

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2021, Public Health England"
__license__ = "MIT"
__version__ = "0.0.1"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    "Connection"
]


CONN_STR = getenv("POSTGRES_CONNECTION_STRING")

logger = getLogger("asyncpg")


class Connection:
    conn: Any

    def __init__(self, conn_str=CONN_STR):
        self.conn_str = conn_str
        self._connection = connect(self.conn_str)

    def __await__(self):
        yield from self._connection.__await__()

    async def __aenter__(self) -> PGConnection:
        self._conn = await self._connection
        await self._conn.set_type_codec(
            'jsonb',
            encoder=dumps,
            decoder=loads,
            schema='pg_catalog'
        )
        # self._conn.add_log_listener(logger)
        return self._conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._conn.close()
