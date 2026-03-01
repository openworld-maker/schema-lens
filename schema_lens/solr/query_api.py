"""Query API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import query_path


def select(client: SolrHttpClient, collection: str, params: dict[str, Any]) -> dict[str, Any]:
    merged = {"wt": "json", **params}
    return client.get_json(query_path(collection), params=merged)
