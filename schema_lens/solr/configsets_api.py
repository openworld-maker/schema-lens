"""Configsets API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import configsets_admin_path


def create_configset(
    client: SolrHttpClient,
    name: str,
    base_configset: str,
) -> dict[str, Any]:
    return client.get_json(
        configsets_admin_path(),
        params={
            "action": "CREATE",
            "name": name,
            "baseConfigSet": base_configset,
            "wt": "json",
        },
    )


def delete_configset(client: SolrHttpClient, name: str) -> dict[str, Any]:
    return client.get_json(
        configsets_admin_path(),
        params={
            "action": "DELETE",
            "name": name,
            "wt": "json",
        },
    )
