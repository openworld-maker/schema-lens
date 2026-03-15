"""HTTP client wrapper with retry semantics."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from schema_lens.errors import SolrRequestError
from schema_lens.http.retry import RETRYABLE_STATUS_CODES, retry_delays

LOGGER = logging.getLogger(__name__)


class SolrHttpClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        cert: str | tuple[str, str] | None = None,
        verify: bool | str = True,
        verbose: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.verbose = verbose
        self.client = httpx.Client(timeout=timeout, headers=headers or {}, cert=cert, verify=verify)

    def close(self) -> None:
        self.client.close()

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        content_body: bytes | None = None,
        headers: dict[str, str] | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = urljoin(self.base_url, path.lstrip("/"))
        last_error: Exception | None = None
        retries = list(retry_delays())
        attempts = [0.0, *retries]

        for attempt, delay in enumerate(attempts, start=1):
            if delay > 0:
                time.sleep(delay)
            started = time.perf_counter()
            try:
                response = self.client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    content=content_body,
                    headers=headers,
                )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                if self.verbose:
                    LOGGER.debug(
                        "HTTP %s %s [%sms] -> %s",
                        method,
                        response.url,
                        elapsed_ms,
                        response.status_code,
                    )

                if response.status_code in RETRYABLE_STATUS_CODES:
                    last_error = SolrRequestError(
                        f"Retryable HTTP status {response.status_code} for {response.url}"
                    )
                    if attempt <= len(retries):
                        continue

                response.raise_for_status()
                if expect_json:
                    return response.json()
                return response.content
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if attempt <= len(retries):
                    continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in RETRYABLE_STATUS_CODES and attempt <= len(retries):
                    last_error = exc
                    continue
                message = (
                    f"HTTP {exc.response.status_code} error for {exc.request.url}: "
                    f"{exc.response.text}"
                )
                raise SolrRequestError(
                    message
                ) from exc
            except ValueError as exc:
                if not expect_json:
                    raise SolrRequestError(f"Invalid non-JSON response handling for {url}") from exc
                raise SolrRequestError(f"Invalid JSON response from {url}") from exc

        raise SolrRequestError(f"Request failed after retries for {url}: {last_error}")

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        return self._request("POST", path, params=params, json_body=json_body)

    def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        return self._request("GET", path, params=params, expect_json=False)

    def post_bytes(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        content_body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        return self._request(
            "POST",
            path,
            params=params,
            content_body=content_body,
            headers=headers,
            expect_json=False,
        )
