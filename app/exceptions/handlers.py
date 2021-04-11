#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from logging import getLogger
from http import HTTPStatus

# 3rd party:
from fastapi import Request
from fastapi.responses import JSONResponse

# Internal:
from app.config import Settings

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'exception_handlers'
]


logger = getLogger(__name__)


async def handle_404(request: Request, exc, **context):
    status = HTTPStatus.NOT_FOUND
    status_code = getattr(status, "value", status.real)
    status_detail = getattr(status, "phrase", "Not Found")

    custom_dims = dict(
        custom_dimensions=dict(
            is_healthcheck=Settings.healthcheck_path in request.url.path,
            url=str(request.url),
            path=str(request.url.path),
            query_string=str(request.query_params),
            status_code=status_code,
            status_detail=status_detail,
            api_environment=Settings.ENVIRONMENT,
            server_location=Settings.server_location,
            is_dev=Settings.DEBUG,
            **context
        )
    )

    logger.warning(exc, extra=custom_dims, exc_info=True)

    return JSONResponse(
        content={
            "status_code": status_code,
            "status_detail": status_detail,
        },
        status_code=status_code
    )


async def handle_500(request: Request, exc, **context):
    if hasattr(exc, "status_code"):
        status_code = getattr(exc, "status_code")
        detail = getattr(exc, "detail", str())
        status_detail = getattr(exc, "phrase", detail)
    else:
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        status_code = getattr(status, "value", status.real)
        status_detail = getattr(status, "phrase", "Internal Server Error")

    custom_dims = dict(
        custom_dimensions=dict(
            is_healthcheck=Settings.healthcheck_path in request.url.path,
            url=str(request.url),
            path=str(request.url.path),
            query_string=str(request.query_params),
            status_code=status_code,
            status_detail=status_detail,
            API_environment=Settings.ENVIRONMENT,
            server_location=Settings.server_location,
            is_dev=Settings.DEBUG,
            **context
        )
    )

    logger.error(exc, extra=custom_dims, exc_info=True)

    return JSONResponse(
        content={
            "status_code": status_code,
            "status_detail": status_detail,
        },
        status_code=status_code
    )


exception_handlers = {
    404: handle_404,
    500: handle_500,
    502: handle_500,
    503: handle_500
}
