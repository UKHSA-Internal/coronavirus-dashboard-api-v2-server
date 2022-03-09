#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from sys import stdout

# 3rd party:
from fastapi import FastAPI
from fastapi.middleware import Middleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from opencensus.trace.samplers import AlwaysOnSampler

# Internal:
from app.utils.assets import add_cloud_role_name
from app.middleware.tracers.starlette import TraceRequestMiddleware
from app.config import Settings
from app.exceptions.handlers import exception_handlers

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'start_app'
]


logger = logging.getLogger("app")

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


def start_app():
    middlewares = [
        Middleware(ProxyHeadersMiddleware, trusted_hosts=Settings.service_domain),
    ]

    if Settings.IS_DEV == 1: # Only monitor when provisioned to the cloud
        middlewares += [
            Middleware(
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
        ]

    if Settings.DEBUG:
        handler = logging.StreamHandler(stdout)

        for log, level in logging_instances:
            log.addHandler(handler)
            log.setLevel(level)

    app = FastAPI(
        title="UK Coronavirus Dashboard - API Service",
        version="2.1.0",
        redoc_url=None,
        openapi_url="/api/v2/openapi.json",
        middleware=middlewares,
        exception_handlers=exception_handlers
    )

    return app
