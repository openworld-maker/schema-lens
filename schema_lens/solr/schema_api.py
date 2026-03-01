"""Schema API functions."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import schema_path


def get_schema(client: SolrHttpClient, collection: str) -> dict[str, Any]:
    return client.get_json(schema_path(collection), params={"wt": "json"})


def post_schema_command(
    client: SolrHttpClient,
    collection: str,
    command: dict[str, Any],
) -> dict[str, Any]:
    return client.post_json(
        schema_path(collection),
        params={"wt": "json"},
        json_body=command,
    )


def replace_field(
    client: SolrHttpClient,
    collection: str,
    field_def: dict[str, Any],
) -> dict[str, Any]:
    return post_schema_command(client, collection, {"replace-field": field_def})


def replace_field_type(
    client: SolrHttpClient, collection: str, field_type_def: dict[str, Any]
) -> dict[str, Any]:
    return post_schema_command(client, collection, {"replace-field-type": field_type_def})
