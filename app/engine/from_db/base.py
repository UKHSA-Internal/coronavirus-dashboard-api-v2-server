#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from logging import getLogger
from typing import AsyncGenerator
from http import HTTPStatus
from functools import partial
from asyncio import sleep
from tempfile import NamedTemporaryFile

# 3rd party:
from orjson import dumps
from aiofiles import open as aio_open

# Internal:
from app.exceptions import NotAvailable
from app.utils.operations import Response, Request
from app.utils.assets import RequestMethod
from app.database import Connection
from app.storage import AsyncStorageClient
from .utils import format_response, cache_response
from .nested import process_nested_data
from .generic import process_generic_data

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'get_data'
]


logger = getLogger('COVID19-APIv2')


# Row limit for DB queries.
RESPONSE_LIMIT = 10_000  # Records per iteration


def log_response(query, arguments):
    """
    Closure for logging DB query information.

    Main function receives the ``query`` and its ``arguments`` and returns
    a function that may be passed to the ``cosmos_client.query_items``
    as the ``response_hook`` keyword argument.
    """
    count = 0

    def process(metadata, results):
        nonlocal count, query

        for item in arguments:
            query = query.replace(item['name'], item['value'])

        custom_dims = dict(
            charge=metadata.get('x-ms-request-charge', None),
            query=query,
            query_raw=query,
            response_count=metadata.get('x-ms-item-count', None),
            path=metadata.get('x-ms-alt-content-path', None),
            parameters=arguments,
            request_round=count
        )

        logger.info(f"DB QUERY: {dumps(custom_dims)}")

    return process


@cache_response
async def process_get_request(*, request: Request, **kwargs) -> AsyncGenerator[bytes, bytes]:
    if len(request.nested_metrics) > 0:
        func = partial(process_nested_data, request=request)
    else:
        func = partial(process_generic_data, request=request)

    prefix, suffix = b"", b""

    if request.format == 'json':
        prefix, suffix = b'{"body":[', b']}'

    # We use cursor movements instead of offset-limit. This is faster
    # as the DB won't have to iterate to fine the offset location.
    async with Connection() as conn, conn.transaction(), conn.transaction():
        # Set query
        cursor = await conn.cursor(request.db_query, *request.db_args)

        # Set limit on cursor
        values = await cursor.fetch(RESPONSE_LIMIT)

        # Yielding the opening chunk, which needs to be separate
        # for data with a different header - e.g. CSV.
        yield prefix + format_response(
            func(values),
            response_type=request.format,
            include_header=True
        )

        # Move cursor forward for the next iteration.
        await cursor.forward(RESPONSE_LIMIT)

        # Yielding the rest of the data.
        while len(values := await cursor.fetch(RESPONSE_LIMIT)) > 0:
            data = func(values)

            yield format_response(
                data,
                response_type=request.format,
                include_header=False
            )

            # Move cursor forward for the next iteration.
            await cursor.forward(RESPONSE_LIMIT)

    # Yielding the closing chunk, which needs to be separate
    # for data with a different ending - e.g. JSON.
    yield suffix


async def from_cache_or_db(request: Request) -> AsyncGenerator[bytes, None]:
    max_wait_cycles = 18  # Max wait: 3 minutes
    wait_period = 10  # seconds
    wait_counter = 1
    async with AsyncStorageClient("apiv2cache", request.path) as blob_client:
        while await blob_client.exists() and wait_counter <= max_wait_cycles:
            # Wait for the blob lease to be release until `max_wait_cycles`
            # is reached or the blob is removed.
            if await blob_client.is_locked():
                await sleep(wait_period)
                wait_counter += 1
                continue

            # Compose a temp file for upload to storage. The temp
            # file needs to be named for asyncio support.
            with NamedTemporaryFile(mode='w+b') as cache_file:
                await blob_client.download_into(cache_file)

                async with aio_open(cache_file.name, mode='rb') as reader:
                    # Read 32 MB chunks
                    while data := await reader.read(2**25):
                        yield data

            return

    # If after 3 minutes, the blob lease is not released,
    # serve the request directly from the database.
    cache_results = wait_counter != max_wait_cycles

    # Run from the database and cache the results.
    async for chunk in process_get_request(request=request, cache_results=cache_results):
        yield chunk


async def get_data(*, request: Request) -> Response:
    content = None

    if request.method == RequestMethod.Get:
        content = from_cache_or_db(request=request)

    if request.method == RequestMethod.Head:
        async with Connection() as conn:
            values = await conn.fetchval(request.db_query, *request.db_args)

        if values is None or not values:
            raise NotAvailable()

    return Response(
        content=content,
        status_code=HTTPStatus.OK.real,
        content_type=request.format,
        release_date=request.release,
        request=request
    )
