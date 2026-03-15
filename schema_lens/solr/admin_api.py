"""Admin API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import luke_path, mbeans_path, metrics_path, system_info_path


def system_info(client: SolrHttpClient) -> dict[str, Any]:
    return client.get_json(system_info_path(), params={"wt": "json"})


def admin_metrics(client: SolrHttpClient, prefix: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"wt": "json"}
    if prefix:
        params["prefix"] = prefix
    return client.get_json(metrics_path(), params=params)


def admin_mbeans(client: SolrHttpClient, category: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"wt": "json", "stats": "true"}
    if category:
        params["cat"] = category
    return client.get_json(mbeans_path(), params=params)


def luke_info(client: SolrHttpClient, collection: str) -> dict[str, Any]:
    return client.get_json(luke_path(collection), params={"wt": "json", "numTerms": "0"})
