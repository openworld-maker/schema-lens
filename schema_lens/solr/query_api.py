"""Query API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import query_json_path, query_path


def select(client: SolrHttpClient, collection: str, params: dict[str, Any]) -> dict[str, Any]:
    merged = {"wt": "json", **params}
    return client.get_json(query_path(collection), params=merged)


def query_json(
    client: SolrHttpClient,
    collection: str,
    json_body: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = {"wt": "json"}
    if isinstance(params, dict):
        merged.update(params)
    return client.post_json(query_json_path(collection), params=merged, json_body=json_body)
