"""Alias swap planning and optional execution."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import collections_admin_path


def get_aliases(client: SolrHttpClient) -> dict[str, str]:
    payload = client.get_json(
        collections_admin_path(),
        params={"action": "LISTALIASES", "wt": "json"},
    )
    aliases = payload.get("aliases", {})
    return {str(k): str(v) for k, v in aliases.items()} if isinstance(aliases, dict) else {}


def build_alias_swap_plan(*, alias: str, source_collection: str, target_collection: str) -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "alias": alias,
        "from_collection": source_collection,
        "to_collection": target_collection,
        "command": {
            "action": "CREATEALIAS",
            "name": alias,
            "collections": target_collection,
        },
    }


def execute_alias_swap(client: SolrHttpClient, *, alias: str, target_collection: str) -> dict[str, Any]:
    return client.get_json(
        collections_admin_path(),
        params={
            "action": "CREATEALIAS",
            "name": alias,
            "collections": target_collection,
            "wt": "json",
        },
    )
