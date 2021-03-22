#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from functools import wraps
from inspect import signature

# 3rd party:
from opencensus.trace.execution_context import get_opencensus_tracer
from opencensus.trace.span import SpanKind

# Internal:

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'trace_async_method_operation',
    'trace_method_operation'
]


def trace_async_method_operation(*cls_attrs, dep_type="name", name="name", **attrs):
    def wrapper(func):
        sig = signature(func)

        @wraps(func)
        async def process(klass, *args, **kwargs):
            nonlocal sig, name, cls_attrs, attrs
            cls_attrs = list(cls_attrs)

            bound_inputs = sig.bind(klass, *args, **kwargs)

            tracer = get_opencensus_tracer()

            if tracer is None:
                return await func(*bound_inputs.args, **bound_inputs.kwargs)

            span = tracer.start_span()
            span.span_kind = SpanKind.UNSPECIFIED
            span.name = getattr(klass, name, None)

            if "operation" in attrs:
                span.name = f'{attrs.pop("operation")} {span.name}'

            dependency_type = getattr(klass, dep_type)
            span.add_attribute('dependency.type', dependency_type)

            if "url" in cls_attrs and dependency_type.lower() == "azure blob":
                cls_attrs.remove("url")
                span.add_attribute(f"{dependency_type}.data", getattr(klass, "url", None))

            if "query" in bound_inputs.arguments:
                span.add_attribute(f"{dependency_type}.query", bound_inputs.arguments['query'])
                span.add_attribute(f"{dependency_type}.method.name", func.__name__)

            for key in cls_attrs:
                span.add_attribute(f"{dependency_type}.{key}", getattr(klass, key, None))

            for key, value in attrs.items():
                span.add_attribute(f"{dependency_type}.{key}", value)

            success = True
            try:
                return await func(klass, *args, **kwargs)
            except Exception as err:
                success = False
                raise err
            finally:
                span.add_attribute(f'{dependency_type}.success', success)
                tracer.end_span()

        return process

    return wrapper


def trace_method_operation(*cls_attrs, dep_type="name", name="name", **attrs):
    def wrapper(func):
        sig = signature(func)

        @wraps(func)
        def process(klass, *args, **kwargs):
            nonlocal sig, name, cls_attrs, attrs
            cls_attrs = list(cls_attrs)

            bound_inputs = sig.bind(klass, *args, **kwargs)

            tracer = get_opencensus_tracer()

            if tracer is None:
                return func(*bound_inputs.args, **bound_inputs.kwargs)

            span = tracer.start_span()
            span.span_kind = SpanKind.UNSPECIFIED
            span.name = getattr(klass, name, None)

            if "operation" in attrs:
                span.name = f'{attrs.pop("operation")} {span.name}'

            dependency_type = getattr(klass, dep_type)
            span.add_attribute('dependency.type', dependency_type)

            if "url" in cls_attrs and dependency_type.lower() == "azure blob":
                cls_attrs.remove("url")
                span.add_attribute(f"{dependency_type}.data", getattr(klass, "url", None))

            if "query" in bound_inputs.arguments:
                span.add_attribute(f"{dependency_type}.query", bound_inputs.arguments['query'])
                span.add_attribute(f"{dependency_type}.method.name", func.__name__)

            for key in cls_attrs:
                span.add_attribute(f"{dependency_type}.{key}", getattr(klass, key, None))

            for key, value in attrs.items():
                span.add_attribute(f"{dependency_type}.{key}", value)

            success = True
            try:
                return func(klass, *args, **kwargs)
            except Exception as err:
                success = False
                raise err
            finally:
                span.add_attribute(f'{dependency_type}.success', success)
                tracer.end_span()

        return process

    return wrapper
