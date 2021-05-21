#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from logging import getLogger
from typing import AsyncGenerator, Union
from http import HTTPStatus
from functools import partial
from asyncio import sleep
from tempfile import NamedTemporaryFile

# 3rd party:
from orjson import dumps

# Internal:
from app.exceptions import NotAvailable
from app.utils.operations import Response, RedirectResponse, Request
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


logger = getLogger('app')


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


async def process_get_request(*, request: Request, **kwargs) -> AsyncGenerator[bytes, bytes]:
    if len(request.nested_metrics) > 0:
        func = partial(process_nested_data, request=request)
    else:
        func = partial(process_generic_data, request=request)

    # We use cursor movements instead of offset-limit. This is faster
    # as the DB won't have to iterate to fine the offset location.
    async with Connection() as conn:
        area_codes = await request.get_query_area_codes(conn)

        header_generated = False

        # Fetching data from the DB.
        for index, codes in enumerate(area_codes):

            result = await conn.fetch(request.db_query, *request.db_args, codes)
            if not len(result):
                continue

            res = format_response(
                func(result),
                response_type=request.format,
                request=request,
                include_header=not header_generated
            )

            yield index, res

            header_generated = True


async def from_cache_or_db(request: Request) -> Union[Response, RedirectResponse]:
    max_wait_cycles = 29  # Max wait: 4 minutes and 50 seconds
    wait_period = 10  # seconds
    wait_counter = 1

    kws = {
        "container": "apiv2cache",
        "path": request.path,
    }

    cache_results = True

    async with AsyncStorageClient(**kws) as blob_client:
        while await blob_client.exists() and wait_counter <= max_wait_cycles:
            props = await blob_client.client.get_blob_tags()

            # Wait for the blob lease to be release until `max_wait_cycles`
            # is reached or the blob is removed.
            lock_status = await blob_client.is_locked()
            if lock_status and props.get("in_progress", '1') == '1':
                await sleep(wait_period)
                wait_counter += 1
                continue
            elif not lock_status and props.get('done', "0") != "1" and props.get('in_progress', '1') == '1':
                await blob_client.delete()
                cache_results = True
                break
            elif props.get('done', "0") == "1" and props.get('in_progress', '1') == '0':
                cache_results = False
                break

    if cache_results:
        await cache_response(process_get_request, request=request)

    if request.format != "xml":
        return RedirectResponse(request, "apiv2cache", request.path)

    with NamedTemporaryFile(mode='w+b') as cache_file:
        async with AsyncStorageClient(kws['container'], kws['path']) as cli:
            await cli.download_into(cache_file)

        return Response(
            content=cache_file.read(),
            status_code=HTTPStatus.OK.real,
            content_type=request.format,
            release_date=request.release,
            request=request
        )


async def get_data(*, request: Request) -> Union[Response, RedirectResponse]:
    content = None

    if request.method == RequestMethod.Get:
        content = await from_cache_or_db(request=request)

    if request.method == RequestMethod.Head:
        async with Connection() as conn:
            values = await conn.fetchval(request.db_query, *request.db_args)

        if values is None or not values:
            raise NotAvailable()

    return content
