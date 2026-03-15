"""Query grouping heuristics for performance analysis."""

from __future__ import annotations

from typing import Any


def classify_query(
    *,
    params: dict[str, Any] | None = None,
    request_mode: str | None = None,
    scenario_mode: str | None = None,
    facet_counts: dict[str, Any] | None = None,
) -> list[str]:
    params = params if isinstance(params, dict) else {}
    labels: list[str] = []

    if scenario_mode == "vector_only":
        labels.append("vector")
    elif scenario_mode == "hybrid":
        labels.append("hybrid")
    else:
        labels.append("lexical")

    if request_mode == "json_request":
        if "queries" in params or "knn" in str(params.get("q", "")).lower():
            if "vector" not in labels and "hybrid" not in labels:
                labels.append("vector")

    fq = params.get("fq")
    if fq:
        labels.append("filter_heavy")
    if facet_counts:
        labels.append("facet_heavy")
    if params.get("sort"):
        labels.append("sort_heavy")

    out: list[str] = []
    for label in labels:
        if label not in out:
            out.append(label)
    return out
