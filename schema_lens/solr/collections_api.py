"""Collections API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import collections_admin_path


def create_collection(
    client: SolrHttpClient,
    name: str,
    num_shards: int = 1,
    replication_factor: int = 1,
    config_name: str = "_default",
) -> dict[str, Any]:
    params = {
        "action": "CREATE",
        "name": name,
        "numShards": num_shards,
        "replicationFactor": replication_factor,
        "collection.configName": config_name,
        "wt": "json",
    }
    return client.get_json(collections_admin_path(), params=params)


def delete_collection(client: SolrHttpClient, name: str) -> dict[str, Any]:
    return client.get_json(
        collections_admin_path(),
        params={"action": "DELETE", "name": name, "wt": "json"},
    )


def cluster_status(client: SolrHttpClient, collection: str) -> dict[str, Any]:
    return client.get_json(
        collections_admin_path(),
        params={"action": "CLUSTERSTATUS", "collection": collection, "wt": "json"},
    )


def collection_config_name(client: SolrHttpClient, collection: str) -> str:
    status = cluster_status(client, collection)
    collections = (
        status.get("cluster", {})
        .get("collections", {})
    )
    config_name = collections.get(collection, {}).get("configName")
    if not config_name:
        raise ValueError(f"Could not determine configName for collection {collection}")
    return str(config_name)
