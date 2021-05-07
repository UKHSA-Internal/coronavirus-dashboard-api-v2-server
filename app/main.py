#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from typing import Optional, List
from json import dumps
from http import HTTPStatus

# 3rd party:
from fastapi import Query, Request as APIRequest
from fastapi.responses import RedirectResponse as APIRedirect, Response as APIResponse

# Internal:
from app.startup import start_app
from app.utils.operations import Response, RedirectResponse, Request
from app.utils.assets import RequestMethod
from app.exceptions import APIException
from app.engine import get_data, run_healthcheck
from app.config import Settings

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'main',
    'app'
]


logger = logging.getLogger("app")

app = start_app()


@app.get("/api/v2/data")
@app.head("/api/v2/data")
async def main(req: APIRequest,
               areaType: str = Query(..., max_length=10, title="Area type"),
               release: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$", title="Release date"),
               metric: List[str] = Query(...),
               format: str = Query("json", regex=r"^csv|jsonl?|xml$", title="Response format"),
               areaCode: Optional[str] = Query(None, max_length=10, title="Area code")):

    request = Request(
        request=req,
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
        response = APIResponse(content=content.encode(), status_code=err)

    if request.method == RequestMethod.Head:
        return APIResponse(
            str(),
            status_code=response.status_code,
            headers=response.headers
        )

    if isinstance(response, RedirectResponse):
        return APIRedirect(
            url=response.location,
            status_code=HTTPStatus.SEE_OTHER.real,
            headers=response.headers
        )

    return APIResponse(
        response.content,
        status_code=HTTPStatus.OK.real,
        headers=response.headers
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
