"""Replay runner for baseline/shadow queries."""

from __future__ import annotations

import logging
from typing import Any

from schema_lens.queries.model import QueryCase
from schema_lens.replay.result_model import QueryDoc, QueryResult
from schema_lens.solr.query_api import select

LOGGER = logging.getLogger(__name__)


def _normalize_fl(value: str | None) -> str:
    if not value:
        return "id,score"
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if "id" not in parts:
        parts.append("id")
    if "score" not in parts:
        parts.append("score")
    return ",".join(parts)


def _build_params(
    query_case: QueryCase,
    request_defaults: dict[str, Any],
    k: int,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    merged.update(request_defaults)

    extra_params = merged.pop("extra_params", None)
    if isinstance(extra_params, dict):
        merged.update(extra_params)

    merged.update(query_case.params)
    merged["rows"] = str(k)
    merged["wt"] = "json"
    merged["fl"] = _normalize_fl(str(merged.get("fl", "id,score")))
    return merged


def _extract_docs(solr_response: dict[str, Any]) -> list[QueryDoc]:
    docs = []
    response_docs = solr_response.get("response", {}).get("docs", [])
    for idx, raw_doc in enumerate(response_docs, start=1):
        doc_id = raw_doc.get("id")
        if doc_id is None:
            continue
        score = raw_doc.get("score")
        docs.append(QueryDoc(id=str(doc_id), score=score, rank=idx))
    return docs


def _extract_meta(solr_response: dict[str, Any]) -> dict[str, Any]:
    return {
        "QTime": solr_response.get("responseHeader", {}).get("QTime"),
        "status": solr_response.get("responseHeader", {}).get("status"),
        "numFound": solr_response.get("response", {}).get("numFound"),
    }


def run_replay(
    *,
    baseline_client: Any,
    baseline_collection: str,
    shadow_client: Any,
    shadow_collection: str,
    queries: list[QueryCase],
    request_defaults: dict[str, Any],
    k: int,
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    failures = 0

    for case in queries:
        baseline_result = QueryResult(query_id=case.id, target="baseline")
        shadow_result = QueryResult(query_id=case.id, target="shadow")

        params = _build_params(case, request_defaults, k)

        try:
            base_resp = select(baseline_client, baseline_collection, params)
            baseline_result.docs = _extract_docs(base_resp)
            baseline_result.raw_response_meta = _extract_meta(base_resp)
        except Exception as exc:  # noqa: BLE001
            baseline_result.error = str(exc)
            failures += 1
            LOGGER.warning("Baseline query failed for query_id=%s: %s", case.id, exc)

        try:
            shadow_resp = select(shadow_client, shadow_collection, params)
            shadow_result.docs = _extract_docs(shadow_resp)
            shadow_result.raw_response_meta = _extract_meta(shadow_resp)
        except Exception as exc:  # noqa: BLE001
            shadow_result.error = str(exc)
            failures += 1
            LOGGER.warning("Shadow query failed for query_id=%s: %s", case.id, exc)

        pairs.append(
            {
                "query": case.to_dict(),
                "baseline": baseline_result.to_dict(),
                "shadow": shadow_result.to_dict(),
            }
        )

    return {
        "k": k,
        "request_defaults": request_defaults,
        "pairs": pairs,
        "stats": {
            "queries_total": len(queries),
            "failures": failures,
        },
    }
