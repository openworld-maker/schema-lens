"""Composite Solr document sampling with export/cursormark modes."""

from __future__ import annotations

from typing import Any

from schema_lens.data.cursormark import sample_docs_cursormark
from schema_lens.data.solr_export import sample_docs_export


def sample_docs_from_solr(
    *,
    client: Any,
    collection: str,
    mode: str = "cursormark",
    query: str = "*:*",
    fl: str = "*",
    sort: str = "id asc",
    sample_n: int = 50000,
    batch_size: int = 500,
) -> tuple[list[dict[str, Any]], str]:
    effective_mode = mode or "cursormark"
    if effective_mode not in {"export", "cursormark"}:
        raise ValueError("mode must be 'export' or 'cursormark'")

    if effective_mode == "export":
        try:
            docs = sample_docs_export(
                client=client,
                collection=collection,
                query=query,
                fl=fl,
                sort=sort,
                sample_n=sample_n,
                batch_size=batch_size,
            )
            if docs:
                return docs, "export"
        except Exception:  # noqa: BLE001
            pass

    docs = sample_docs_cursormark(
        client=client,
        collection=collection,
        query=query,
        fl=fl,
        sort=sort,
        sample_n=sample_n,
        batch_size=batch_size,
    )
    return docs, "cursormark"

