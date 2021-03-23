#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from typing import Optional, List
from inspect import isasyncgen
from json import dumps
from http import HTTPStatus
from sys import stdout

# 3rd party:
from fastapi import (
    FastAPI, Query,
    Request as APIRequest,
    Response as APIResponse,
)
from fastapi.responses import StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from opencensus.trace.samplers import AlwaysOnSampler

# Internal: 
from app.utils.operations import Response, Request
from app.utils.assets import RequestMethod, add_cloud_role_name
from app.exceptions import APIException
from app.engine import get_data, run_healthcheck
from app.middleware.tracers.starlette import TraceRequestMiddleware
from app.config import Settings
from app.exceptions.handlers import exception_handlers

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'main'
]


logger = logging.getLogger(__name__)

logging_instances = [
    [logger, logging.INFO],
    [logging.getLogger('uvicorn'), logging.WARNING],
    [logging.getLogger('uvicorn.access'), logging.WARNING],
    [logging.getLogger('uvicorn.error'), logging.ERROR],
    [logging.getLogger('azure'), logging.WARNING],
    [logging.getLogger('gunicorn'), logging.WARNING],
    [logging.getLogger('gunicorn.access'), logging.WARNING],
    [logging.getLogger('gunicorn.error'), logging.ERROR],
    [logging.getLogger('asyncpg'), logging.WARNING],
]


app = FastAPI(
    title="UK Coronavirus Dashboard - API Service",
    version="2.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/v2/openapi.json",
    exception_handlers=exception_handlers
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=Settings.service_domain)

app.add_middleware(
    TraceRequestMiddleware,
    sampler=AlwaysOnSampler(),
    instrumentation_key=Settings.instrumentation_key,
    cloud_role_name=add_cloud_role_name,
    extra_attrs=dict(
        environment=Settings.ENVIRONMENT,
        server_location=Settings.server_location
    ),
    logging_instances=logging_instances
)

app.add_middleware(GZipMiddleware)


@app.get("/api/v2/data")
@app.head("/api/v2/data")
async def main(req: APIRequest,
               areaType: str = Query(..., max_length=10, title="Area type"),
               release: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$", title="Release date"),
               metric: List[str] = Query(...),
               format: str = Query("json", regex=r"^csv|jsonl?|xml$", title="Response format"),
               areaCode: Optional[str] = Query(None, max_length=10, title="Area code")):

    request = Request(
        area_type=areaType,
        release=release,
        format=format,
        metric=metric,
        area_code=areaCode,
        method=req.method,
        url=req.url
    )

    try:
        response = await get_data(request=request)
    except APIException as err:
        logging.info(err)
        content = dumps({"response": err.message, "status_code": err.code})
        response = Response(content=content.encode(), status_code=err.code)

    except Exception as err:
        # A generic exception may contain sensitive data and must
        # never be included in the response.
        logger.exception(err)
        err = HTTPStatus.INTERNAL_SERVER_ERROR
        content = dumps({
            "response": (
                "An internal error occurred whilst processing your request, please "
                "try again. If the problem persists, please report as an issue and "
                "include your request."
            ),
            "status_code": err,
            "status": getattr(err, 'phrase')
        })
        response = Response(content=content.encode(), status_code=err)

    if request.method == RequestMethod.Head or not isasyncgen(response.content):
        return APIResponse(
            response.content,
            status_code=response.status_code,
            headers=await response.headers
        )

    return StreamingResponse(
        response.content,
        status_code=response.status_code,
        headers=await response.headers
    )


@app.get(f"/api/v2/{Settings.healthcheck_path}")
@app.head(f"/api/v2/{Settings.healthcheck_path}")
async def healthcheck(req: APIRequest):
    try:
        response = await run_healthcheck()
    except Exception() as err:
        logger.exception(err)
        raise err

    if req.method == RequestMethod.Head:
        return APIResponse(None, status_code=HTTPStatus.NO_CONTENT.real)

    return response


if __name__ == "__main__":
    from uvicorn import run as uvicorn_run

    uvicorn_run(app, port=1244)
