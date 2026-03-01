"""Fetch debug explain bundles for risky queries."""

from __future__ import annotations

import logging
from typing import Any

from schema_lens.solr.query_api import select

LOGGER = logging.getLogger(__name__)


def _pick_doc_ids(diff: dict[str, Any], max_docs: int) -> list[str]:
    doc_ids: list[str] = []
    doc_ids.extend(diff.get("dropped_docs", []))
    moved = sorted(diff.get("moved_docs", []), key=lambda d: abs(d.get("delta", 0)), reverse=True)
    doc_ids.extend([m["id"] for m in moved if "id" in m])
    doc_ids.extend(diff.get("new_docs", []))

    out = []
    seen = set()
    for doc_id in doc_ids:
        if doc_id not in seen:
            out.append(doc_id)
            seen.add(doc_id)
        if len(out) >= max_docs:
            break
    return out


def _fetch_explain(
    client: Any,
    collection: str,
    query_params: dict[str, Any],
    k: int,
    doc_id: str,
) -> tuple[Any, Any, dict[str, Any] | None]:
    return _fetch_explain_internal(
        client=client,
        collection=collection,
        query_params=query_params,
        k=k,
        doc_id=doc_id,
        structured=False,
    )


def _fetch_explain_internal(
    *,
    client: Any,
    collection: str,
    query_params: dict[str, Any],
    k: int,
    doc_id: str,
    structured: bool,
) -> tuple[Any, Any, dict[str, Any] | None]:
    params = dict(query_params)
    if structured:
        params["debug"] = "results"
        params["debug.explain.structured"] = "true"
    else:
        params["debugQuery"] = "true"
    params["fl"] = "id,score"
    params["rows"] = str(k)
    params["wt"] = "json"
    resp = select(client, collection, params)
    debug = resp.get("debug", {})
    explain = debug.get("explain", {}).get(doc_id)
    explain_structured = explain if isinstance(explain, dict) else None
    return explain, explain_structured, debug


def fetch_explains(
    *,
    baseline_client: Any,
    baseline_collection: str,
    shadow_client: Any,
    shadow_collection: str,
    replay_pairs: list[dict[str, Any]],
    diffs: list[dict[str, Any]],
    k: int,
    max_queries: int,
    max_docs_per_query: int,
    structured: bool = False,
) -> list[dict[str, Any]]:
    by_qid = {pair.get("query", {}).get("id"): pair for pair in replay_pairs}

    ranked = sorted(
        diffs,
        key=lambda d: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(d.get("risk_severity"), 3),
            d.get("topk_overlap_count", k),
            1.0 if d.get("kendall_tau") is None else d.get("kendall_tau"),
        ),
    )

    bundles: list[dict[str, Any]] = []

    for diff in ranked[:max_queries]:
        if diff.get("risk_severity") == "LOW":
            continue

        query_id = diff.get("query_id")
        pair = by_qid.get(query_id)
        if not pair:
            continue

        query = pair.get("query", {})
        params = query.get("params", {})
        doc_ids = _pick_doc_ids(diff, max_docs_per_query)

        for doc_id in doc_ids:
            try:
                base_explain, base_structured, base_debug = _fetch_explain_internal(
                    client=baseline_client,
                    collection=baseline_collection,
                    query_params=params,
                    k=k,
                    doc_id=doc_id,
                    structured=structured,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Explain fetch failed on baseline for q=%s doc=%s: %s",
                    query_id,
                    doc_id,
                    exc,
                )
                base_explain = None
                base_structured = None
                base_debug = None

            try:
                shadow_explain, shadow_structured, shadow_debug = _fetch_explain_internal(
                    client=shadow_client,
                    collection=shadow_collection,
                    query_params=params,
                    k=k,
                    doc_id=doc_id,
                    structured=structured,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Explain fetch failed on shadow for q=%s doc=%s: %s",
                    query_id,
                    doc_id,
                    exc,
                )
                shadow_explain = None
                shadow_structured = None
                shadow_debug = None

            bundles.append(
                {
                    "query_id": query_id,
                    "doc_id": doc_id,
                    "baseline_explain_raw": base_explain,
                    "shadow_explain_raw": shadow_explain,
                    "baseline_explain_structured": base_structured,
                    "shadow_explain_structured": shadow_structured,
                    "baseline_debug": base_debug,
                    "shadow_debug": shadow_debug,
                }
            )

    return bundles
