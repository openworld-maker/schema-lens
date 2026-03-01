"""Update API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import update_path


def post_docs(
    client: SolrHttpClient,
    collection: str,
    docs: list[dict[str, Any]],
) -> dict[str, Any]:
    return client.post_json(
        update_path(collection),
        params={"commit": "true", "wt": "json"},
        json_body=docs,
    )
