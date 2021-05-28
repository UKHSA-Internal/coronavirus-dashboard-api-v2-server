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
from asyncpg import connect, Connection as BaseConnection
from asyncpg.transaction import Transaction as BaseTransaction
from orjson import loads, dumps

# Internal:
from app.middleware.tracers.utils import trace_async_method_operation, trace_method_operation

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
DB_NAME = "database"

logger = getLogger("asyncpg")


class Transaction(BaseTransaction):
    _name = "postgresql"
    _account_name = DB_NAME

    @trace_async_method_operation(
        name="_account_name",
        dep_type="_name",
        action="transaction_start"
    )
    async def start(self):
        return await super(Transaction, self).start()

    @trace_async_method_operation(
        name="_account_name",
        dep_type="_name",
        action="transaction_commit"
    )
    async def commit(self):
        return await super(Transaction, self).commit()

    @trace_async_method_operation(
        name="_account_name",
        dep_type="_name",
        action="transaction_rollback"
    )
    async def rollback(self):
        return await super(Transaction, self).rollback()


class Connection:
    conn: Any
    _name = "postgresql"
    _account_name = DB_NAME

    def __init__(self, conn_str=CONN_STR):
        self.conn_str = conn_str
        self._connection = connect(self.conn_str, statement_cache_size=0)

    def __await__(self):
        yield from self._connection.__await__()

    async def __aenter__(self) -> BaseConnection:
        self._conn = await self._connection
        await self._conn.set_type_codec(
            'jsonb',
            encoder=dumps,
            decoder=loads,
            schema='pg_catalog'
        )
        # self._conn.add_log_listener(logger)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._conn.close()

    @trace_async_method_operation(
        name="_account_name",
        dep_type="_name",
        action="connection_fetchval"
    )
    async def fetchval(self, query, *args, **kwargs):
        return await self._conn.fetchval(query, *args, **kwargs)

    @trace_async_method_operation(
        name="_account_name",
        dep_type="_name",
        action="connection_fetch"
    )
    async def fetch(self, query, *args, **kwargs):
        return await self._conn.fetch(query, *args, **kwargs)

    @trace_async_method_operation(
        name="_account_name",
        dep_type="_name",
        action="connection_fetchrow"
    )
    async def fetchrow(self, query, *args, **kwargs):
        return await self._conn.fetchrow(query, *args, **kwargs)

    @trace_method_operation(
        name="_account_name",
        dep_type="_name",
        action="transaction_open"
    )
    def transaction(self, *, isolation=None, readonly=False, deferrable=False):
        self._conn._check_open()
        return Transaction(self._conn, isolation=None, readonly=False, deferrable=False)

    @trace_method_operation(
        name="_account_name",
        dep_type="_name",
        action="transaction_acquire"
    )
    def cursor(self, *args, **kwargs):
        self._conn._check_open()
        return self._conn.cursor(*args, **kwargs)
