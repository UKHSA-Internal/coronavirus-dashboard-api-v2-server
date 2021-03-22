#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from urllib.parse import urlparse
from json import dumps

# 3rd party:
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.ext.azure.common import utils
from opencensus.trace.span import SpanKind
from opencensus.ext.azure.common.protocol import (
    Data,
    Envelope,
    RemoteDependency,
    Request,
)

# Internal: 

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'Exporter'
]


class Exporter(AzureExporter):
    def span_data_to_envelope(self, sd):
        envelope = Envelope(
            iKey=self.options.instrumentation_key,
            tags=dict(utils.azure_monitor_context),
            time=sd.start_time,
        )

        predefined_props = set()

        envelope.tags['ai.operation.id'] = sd.context.trace_id
        if sd.parent_span_id:
            envelope.tags['ai.operation.parentId'] = '{}'.format(sd.parent_span_id)
        if sd.span_kind == SpanKind.SERVER:
            envelope.name = 'Microsoft.ApplicationInsights.Request'
            data = Request(
                id='{}'.format(sd.span_id),
                duration=utils.timestamp_to_duration(
                    sd.start_time,
                    sd.end_time,
                ),
                responseCode=str(sd.status.code),
                success=False,  # Modify based off attributes or status
                properties={},
            )
            envelope.data = Data(baseData=data, baseType='RequestData')
            data.name = ''
            if 'http.method' in sd.attributes:
                data.name = sd.attributes['http.method']
            if 'http.route' in sd.attributes:
                data.name = f"{data.name} {sd.attributes['http.route']}"
                envelope.tags['ai.operation.name'] = data.name
                data.properties['request.name'] = data.name
            elif 'http.path' in sd.attributes:
                data.properties['request.name'] = f"{data.name} {sd.attributes['http.path']}"
            if 'http.url' in sd.attributes:
                data.url = sd.attributes['http.url']
                data.properties['request.url'] = sd.attributes['http.url']
            if 'http.status_code' in sd.attributes:
                status_code = sd.attributes['http.status_code']
                data.responseCode = str(status_code)
                data.success = 200 <= status_code < 400
            elif sd.status.code == 0:
                data.success = True
        else:
            envelope.name = 'Microsoft.ApplicationInsights.RemoteDependency'
            data = RemoteDependency(
                name=sd.name,  # TODO
                id='{}'.format(sd.span_id),
                resultCode=str(sd.status.code),
                duration=utils.timestamp_to_duration(
                    sd.start_time,
                    sd.end_time,
                ),
                success=False,  # Modify based off attributes or status
                properties={},
            )

            envelope.data = Data(baseData=data, baseType='RemoteDependencyData')

            if sd.span_kind == SpanKind.CLIENT:
                data.type = sd.attributes.get('component')
                if 'http.url' in sd.attributes:
                    url = sd.attributes['http.url']
                    # TODO: error handling, probably put scheme as well
                    data.data = url
                    parse_url = urlparse(url)
                    # target matches authority (host:port)
                    data.target = parse_url.netloc
                    if 'http.method' in sd.attributes:
                        # name is METHOD/path
                        data.name = f"{sd.attributes['http.method']}  {parse_url.path}"
                if 'http.status_code' in sd.attributes:
                    status_code = sd.attributes["http.status_code"]
                    data.resultCode = str(status_code)
                    data.success = 200 <= status_code < 400
                elif sd.status.code == 0:
                    data.success = True

            elif "dependency.type" in sd.attributes:
                data.type = sd.attributes.pop("dependency.type")
                for key in list(sd.attributes):
                    if key == f"{data.type}.success":
                        data.success = sd.attributes.pop(key)
                        sd.attributes[f"status_code"] = 200 if data.success else 500
                        data.resultCode = str(sd.attributes[f"status_code"])
                        predefined_props.add(key)
                        continue
                    elif key == f"{data.type}.target":
                        data.target = sd.attributes.pop(key)
                        predefined_props.add(key)
                        continue
                    elif key == f"{data.type}.data":
                        data.data = sd.attributes.pop(key)
                        predefined_props.add(key)
                        continue

                    if "error" in key:
                        data.success = False

                    trimmed_key = key.removeprefix(f"{data.type}.")
                    data.properties[trimmed_key] = sd.attributes.get(key)
                    predefined_props.add(key)

                # if f"{data.type}.query" in sd.attributes:
                #     data.data = sd.attributes.pop(f"{data.type}.query")
                # if f"{data.type}.error" in sd.attributes:
                #     data.success = False
                #     data.properties["error"] = sd.attributes.pop(f"{data.type}.error")

            else:
                data.type = 'INPROC'
                data.success = True
        if sd.links:
            links = []
            for link in sd.links:
                links.append({
                    "operation_Id": link.trace_id,
                    "id": link.span_id
                })
            data.properties["_MS.links"] = dumps(links)

        # TODO: tracestate, tags
        for key in sd.attributes:
            # This removes redundant data from ApplicationInsights
            if key.startswith('http.') or key in predefined_props:
                continue
            data.properties[key] = sd.attributes[key]
        return envelope
