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
    Response as APIResponse
)
from fastapi.responses import StreamingResponse

# Internal: 
from app.utils.operations import Response, Request
from app.exceptions import APIException
from app.engine import get_data

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'main'
]


logger = logging.getLogger('COVID19-APIv2')


def setup_logging():
    formatter = logging.Formatter('[%(asctime)s] %(name)s: %(levelname)s | %(message)s')

    handler = logging.StreamHandler(stdout)
    handler.setFormatter(formatter)

    loggers_instances = {
        logger,
        logging.getLogger('uvicorn'),
        logging.getLogger('uvicorn.access'),
        logging.getLogger('uvicorn.error'),
        logging.getLogger('azure'),
        logging.getLogger('gunicorn'),
        logging.getLogger('gunicorn.access'),
        logging.getLogger('gunicorn.error'),
        logging.getLogger('asyncpg'),
    }

    for logger_inst in loggers_instances:
        logger_inst.setLevel(logging.INFO)
        logger_inst.addHandler(handler)


app = FastAPI(
    title="UK Coronavirus Dashboard - API Service",
    version="2.1.0",
    docs_url=None,
    redoc_url=None,
    root_path="/api/v2/",
    openapi_url="/api/v2/openapi.json",
    on_startup=[setup_logging]
)


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

    if request.method == "HEAD" or not isasyncgen(response.content):
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


if __name__ == "__main__":
    from uvicorn import run as uvicorn_run

    uvicorn_run(app, port=1244)
