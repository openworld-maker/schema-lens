"""Admin API helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import system_info_path


def system_info(client: SolrHttpClient) -> dict[str, Any]:
    return client.get_json(system_info_path(), params={"wt": "json"})
