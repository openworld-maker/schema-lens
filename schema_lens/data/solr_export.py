"""Export-handler based Solr document sampling."""

from __future__ import annotations

from typing import Any


def sample_docs_export(
    *,
    client: Any,
    collection: str,
    query: str,
    fl: str,
    sort: str,
    sample_n: int,
    batch_size: int = 500,
) -> list[dict[str, Any]]:
    params = {
        "q": query,
        "fl": fl,
        "sort": sort,
        "rows": str(min(sample_n, batch_size)),
        "wt": "json",
    }
    resp = client.get_json(f"{collection}/export", params=params)
    docs = resp.get("response", {}).get("docs", [])
    if not isinstance(docs, list):
        return []
    return [doc for doc in docs if isinstance(doc, dict)][:sample_n]

