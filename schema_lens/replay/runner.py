"""Replay runner for baseline/shadow queries."""

from __future__ import annotations

import logging
from typing import Any

from schema_lens.compare.facets import parse_facet_fields
from schema_lens.perf.timer import timed_call
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
    capture_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    merged.update(request_defaults)

    extra_params = merged.pop("extra_params", None)
    if isinstance(extra_params, dict):
        merged.update(extra_params)

    if isinstance(query_case.params, dict):
        merged.update(query_case.params)
    merged["rows"] = str(k)
    merged["wt"] = "json"
    merged["fl"] = _normalize_fl(str(merged.get("fl", "id,score")))

    capture_cfg = capture_cfg or {}
    facets_cfg = capture_cfg.get("facets", {}) if isinstance(capture_cfg, dict) else {}
    if isinstance(facets_cfg, dict) and facets_cfg.get("enabled"):
        fields = facets_cfg.get("fields", [])
        if isinstance(fields, list) and fields:
            merged["facet"] = "true"
            merged["facet.field"] = [str(field) for field in fields]
            merged["facet.limit"] = str(int(facets_cfg.get("limit", 20)))
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


def _extract_facet_counts(solr_response: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    facet_fields = (
        solr_response.get("facet_counts", {}).get("facet_fields", {})
    )
    if not isinstance(facet_fields, dict):
        return out
    for field, raw_counts in facet_fields.items():
        parsed = parse_facet_fields(raw_counts)
        out[str(field)] = parsed
    return out


def run_replay(
    *,
    baseline_client: Any,
    baseline_collection: str,
    shadow_client: Any,
    shadow_collection: str,
    queries: list[QueryCase],
    request_defaults: dict[str, Any],
    k: int,
    capture_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    failures = 0

    for case in queries:
        baseline_result = QueryResult(query_id=case.id, target="baseline")
        shadow_result = QueryResult(query_id=case.id, target="shadow")

        params = _build_params(case, request_defaults, k, capture_cfg)

        try:
            base_resp, base_elapsed = timed_call(
                select,
                baseline_client,
                baseline_collection,
                params,
            )
            baseline_result.docs = _extract_docs(base_resp)
            baseline_result.raw_response_meta = _extract_meta(base_resp)
            baseline_result.raw_response_meta["client_latency_ms"] = base_elapsed
            baseline_result.facet_counts = _extract_facet_counts(base_resp)
        except Exception as exc:  # noqa: BLE001
            baseline_result.error = str(exc)
            failures += 1
            LOGGER.warning("Baseline query failed for query_id=%s: %s", case.id, exc)

        try:
            shadow_resp, shadow_elapsed = timed_call(
                select,
                shadow_client,
                shadow_collection,
                params,
            )
            shadow_result.docs = _extract_docs(shadow_resp)
            shadow_result.raw_response_meta = _extract_meta(shadow_resp)
            shadow_result.raw_response_meta["client_latency_ms"] = shadow_elapsed
            shadow_result.facet_counts = _extract_facet_counts(shadow_resp)
        except Exception as exc:  # noqa: BLE001
            shadow_result.error = str(exc)
            failures += 1
            LOGGER.warning("Shadow query failed for query_id=%s: %s", case.id, exc)

        pairs.append(
            {
                "query": case.to_dict(),
                "effective_params": params,
                "baseline": baseline_result.to_dict(),
                "shadow": shadow_result.to_dict(),
            }
        )

    return {
        "k": k,
        "request_defaults": request_defaults,
        "capture": capture_cfg or {},
        "pairs": pairs,
        "stats": {
            "queries_total": len(queries),
            "failures": failures,
        },
    }
