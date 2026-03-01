from __future__ import annotations

import httpx
import pytest

from schema_lens.errors import SolrRequestError
from schema_lens.http.client import SolrHttpClient


def _resp(status: int, url: str, payload: str):
    request = httpx.Request("GET", url)
    return httpx.Response(status, content=payload.encode("utf-8"), request=request)


def test_http_client_retries_retryable_status(monkeypatch):
    client = SolrHttpClient("http://localhost:8983/solr")
    responses = [
        _resp(503, "http://localhost:8983/solr/x", '{"err":1}'),
        _resp(200, "http://localhost:8983/solr/x", '{"ok": true}'),
    ]

    monkeypatch.setattr("schema_lens.http.client.retry_delays", lambda: [0.0])
    monkeypatch.setattr("schema_lens.http.client.time.sleep", lambda _d: None)

    def fake_request(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(client.client, "request", fake_request)

    out = client.get_json("x")
    assert out["ok"] is True


def test_http_client_invalid_json_raises(monkeypatch):
    client = SolrHttpClient("http://localhost:8983/solr")

    monkeypatch.setattr(
        client.client,
        "request",
        lambda *_a, **_k: _resp(200, "http://x", "not-json"),
    )

    with pytest.raises(SolrRequestError, match="Invalid JSON response"):
        client.get_json("x")


def test_http_client_non_retryable_http_error(monkeypatch):
    client = SolrHttpClient("http://localhost:8983/solr")

    monkeypatch.setattr(
        client.client,
        "request",
        lambda *_a, **_k: _resp(400, "http://localhost:8983/solr/x", '{"error":"bad"}'),
    )

    with pytest.raises(SolrRequestError, match="HTTP 400"):
        client.get_json("x")
