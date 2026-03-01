"""CursorMark-based Solr document sampling."""

from __future__ import annotations

from typing import Any

from schema_lens.solr.query_api import select


def sample_docs_cursormark(
    *,
    client: Any,
    collection: str,
    query: str,
    fl: str,
    sort: str,
    sample_n: int,
    batch_size: int = 500,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    cursor = "*"
    prev_cursor = None

    while len(docs) < sample_n:
        params = {
            "q": query,
            "fl": fl,
            "sort": sort,
            "rows": str(min(batch_size, sample_n - len(docs))),
            "cursorMark": cursor,
            "wt": "json",
        }
        resp = select(client, collection, params)
        batch = resp.get("response", {}).get("docs", [])
        if not isinstance(batch, list) or not batch:
            break

        for doc in batch:
            if isinstance(doc, dict):
                docs.append(doc)
                if len(docs) >= sample_n:
                    break

        next_cursor = resp.get("nextCursorMark")
        if not isinstance(next_cursor, str):
            break
        prev_cursor, cursor = cursor, next_cursor
        if cursor == prev_cursor:
            break

    return docs

