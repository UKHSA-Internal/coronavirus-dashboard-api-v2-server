#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from typing import Dict, Iterable, Union

# 3rd party:
from starlette.requests import Request

from starlette.middleware.base import BaseHTTPMiddleware

from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.trace.tracer import Tracer
from opencensus.trace.span import SpanKind
from opencensus.trace.attributes_helper import COMMON_ATTRIBUTES
from opencensus.trace import config_integration
from opencensus.trace.propagation.trace_context_http_header_format import TraceContextPropagator
from opencensus.trace.execution_context import get_opencensus_tracer, get_current_span

# Internal:
from ..azure.exporter import Exporter

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'TraceRequestMiddleware'
]


HTTP_URL = COMMON_ATTRIBUTES['HTTP_URL']
HTTP_STATUS_CODE = COMMON_ATTRIBUTES['HTTP_STATUS_CODE']
HTTP_HOST = COMMON_ATTRIBUTES['HTTP_HOST']
HTTP_METHOD = COMMON_ATTRIBUTES['HTTP_METHOD']
HTTP_PATH = COMMON_ATTRIBUTES['HTTP_PATH']
HTTP_ROUTE = COMMON_ATTRIBUTES['HTTP_ROUTE']


config_integration.trace_integrations(['logging'])
config_integration.trace_integrations(['requests'])


logger = logging.getLogger(__name__)


class TraceRequestMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, sampler, instrumentation_key, cloud_role_name,
                 extra_attrs: Dict[str, str],
                 logging_instances: Iterable[Iterable[Union[logging.Logger, int]]]):

        self.exporter = Exporter(connection_string=instrumentation_key)
        self.exporter.add_telemetry_processor(cloud_role_name)

        self.app = app

        self.sampler = sampler
        self.extra_attrs = extra_attrs

        self.handler = AzureLogHandler(connection_string=instrumentation_key)

        self.handler.add_telemetry_processor(cloud_role_name)
        super(TraceRequestMiddleware, self).__init__(app)

        for log, level in logging_instances:
            log.addHandler(self.handler)
            log.setLevel(level)

    async def dispatch(self, request: Request, call_next):
        propagator = TraceContextPropagator()
        span_context = propagator.from_headers(dict(request.headers))

        tracer = Tracer(
            exporter=self.exporter,
            sampler=self.sampler,
            span_context=span_context,
            propagator=propagator
        )

        try:
            # tracer.span_context.trace_options.set_enabled(True)

            with tracer.span(f"[{request.method}] {request.url}") as span:
                span.span_kind = SpanKind.SERVER
                # if "traceparent" not in request.headers:
                #     trace_ctx = span.context_tracer
                #     trace_options = tracer.span_context.trace_options.trace_options_byte
                #     trace_id = trace_ctx.trace_id
                #     trace_parent = f"00-{trace_id}-{span.span_id}-0{trace_options}"
                # else:
                #     trace_parent = request.headers['traceparent']

                span.add_attribute(HTTP_URL, str(request.url))
                span.add_attribute(HTTP_HOST, request.url.hostname)
                span.add_attribute(HTTP_METHOD, request.method)
                span.add_attribute(HTTP_PATH, request.url.path)
                span.add_attribute(HTTP_ROUTE, request.url.path)
                span.add_attribute("x_forwarded_host", request.headers.get("x_forwarded_host"))

                for key, value in self.extra_attrs.items():
                    span.add_attribute(key, value)

                response = await call_next(request)
                # response.headers['traceparent'] = trace_parent

                span.add_attribute(HTTP_STATUS_CODE, response.status_code)

            return response

        except Exception as err:
            logger.error(err, exc_info=True)
        finally:
            tracer.finish()
