"""Document sampling helpers."""

from __future__ import annotations

from typing import Any


def sample_docs(docs: list[dict[str, Any]], sample_n: int | None) -> list[dict[str, Any]]:
    if sample_n is None or sample_n <= 0:
        return docs
    return docs[:sample_n]
