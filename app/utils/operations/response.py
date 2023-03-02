#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import Union, AsyncGenerator, Dict
from datetime import datetime, date

# 3rd party:

# Internal:
from app.config import Settings
from ..assets import get_latest_timestamp
from .request import Request

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'Response',
    "RedirectResponse"
]


API_PREFIX = "/api/"
API_URL = Settings.service_domain

ResponseContentType = Union[None, bytes, AsyncGenerator[bytes, None]]


class RedirectResponse:
    _content_types_lookup = {
        'json': 'application/vnd.PHE-COVID19.v2+json; charset=utf-8',
        'jsonl': 'application/vnd.PHE-COVID19.v2+jsonl; charset=utf-8',
        'xml': 'application/vnd.PHE-COVID19.v1+json; charset=utf-8',
        'csv': 'text/csv; charset=utf-8'
    }

    def __init__(self, request, container, path):
        host: str = request.base_request.headers.get("X-Forwarded-Host", API_URL)
        host = host.removeprefix("https://").removeprefix("api.")

        # TODO: remove this IF statement when routing rule for rr-apiv2cache frontend
        #       domain name has been change
        self.location = (
            f"https://api.{host}/downloads/{container}/{path}"
            if not host.startswith("sandbox")
            else f"https://api-{host}/downloads/{container}/{path}"
        )

        permalink = f"https://{API_URL}/apiv2cache/{request.path}"

        headers = {
            'Content-Type': self._content_types_lookup[request.format]
        }

        self.headers = headers.update({
            "Cache-Control": "public, max-age=90, must-revalidate",
            "Content-Location": permalink,
            "Content-Language": "en-GB"
        })


class Response:
    _content: ResponseContentType
    _request: Request
    status_code: int
    headers: Dict[str, str]
    _latest_timestamp: Union[datetime, None] = None

    _content_types_lookup = {
        'json': 'application/vnd.PHE-COVID19.v2+json; charset=utf-8',
        'jsonl': 'application/vnd.PHE-COVID19.v2+jsonl; charset=utf-8',
        'xml': 'application/vnd.PHE-COVID19.v1+json; charset=utf-8',
        'csv': 'text/csv; charset=utf-8'
    }

    def __init__(self, content: ResponseContentType, status_code: int,
                 release_date: Union[date, None] = None, content_type: str = 'json',
                 request: Union[Request, None] = None):
        self._content = content
        self.status_code = status_code
        self._content_type = content_type
        self._request = request
        self._release_date = release_date

    @property
    async def latest_timestamp(self) -> Union[datetime, None]:
        if self._latest_timestamp is None:
            self._latest_timestamp = await get_latest_timestamp(self._request)
        return self._latest_timestamp

    @property
    def headers(self):
        headers = {
            'Content-Type': self._content_types_lookup[self._content_type]
        }

        if self._content is not None:
            headers['Content-Disposition'] = (
                f'attachment; filename="{self._request.area_type}_{self._release_date:%Y-%m-%d}.{self._content_type}"'
            )

        # Additional headers for successful responses.
        if self.status_code < 400:
            url_path = self._request.url.path.removeprefix(API_PREFIX)
            permalink = f"https://{API_URL}/{url_path}?{self._request.url.query}"

            headers.update({
                "Cache-Control": "public, max-age=90, must-revalidate",
                "Content-Location": permalink,
                "Content-Language": "en-GB"
            })

        return headers

    @property
    def content(self):
        return self._content
