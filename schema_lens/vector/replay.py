"""Scenario-based replay runner for vector and hybrid simulations."""

from __future__ import annotations

import time
from typing import Any

from schema_lens.queries.model import QueryCase
from schema_lens.solr.query_api import query_json, select
from schema_lens.vector.blend import blend_rankings
from schema_lens.vector.model import VectorRuntimeConfig, VectorScenario
from schema_lens.vector.query_builder import (
    build_lexical_request,
    build_vector_request,
    detect_native_hybrid_request,
)


def _flatten_defaults(request_defaults: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if not isinstance(request_defaults, dict):
        return flattened
    flattened.update(request_defaults)
    extra = flattened.pop("extra_params", None)
    if isinstance(extra, dict):
        flattened.update(extra)
    return flattened


def _extract_docs(solr_response: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for idx, row in enumerate(solr_response.get("response", {}).get("docs", []), start=1):
        doc_id = row.get("id")
        if doc_id is None:
            continue
        docs.append(
            {
                "id": str(doc_id),
                "score": row.get("score"),
                "rank": idx,
            }
        )
        if len(docs) >= limit:
            break
    return docs


def _extract_meta(solr_response: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    header = solr_response.get("responseHeader", {})
    response = solr_response.get("response", {})
    return {
        "status": header.get("status"),
        "QTime": header.get("QTime"),
        "numFound": response.get("numFound"),
        "elapsed_ms": round(elapsed_ms, 3),
    }


def _execute_request(
    *,
    client: Any,
    collection: str,
    request: dict[str, Any],
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    mode = request.get("mode")
    started = time.perf_counter()
    try:
        if mode == "json_request":
            response = query_json(
                client,
                collection,
                json_body=request.get("json_body", {}),
                params=request.get("params", {}),
            )
        else:
            response = select(client, collection, request.get("params", {}))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return _extract_docs(response, limit), _extract_meta(response, elapsed_ms), None
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return [], {"elapsed_ms": round(elapsed_ms, 3)}, str(exc)


def _run_hybrid_client(
    *,
    client: Any,
    collection: str,
    query_case: QueryCase,
    scenario: VectorScenario,
    vector_cfg: VectorRuntimeConfig,
    request_defaults: dict[str, Any],
    top_k: int,
    candidate_pool: int,
) -> dict[str, Any]:
    scenario_knn = scenario.knn if isinstance(scenario.knn, dict) else {}
    scenario_blend = scenario.blend if isinstance(scenario.blend, dict) else {}

    lexical_request = build_lexical_request(
        query_case=query_case,
        rows=candidate_pool,
        base_defaults=request_defaults,
        lexical_overrides=scenario.lexical,
    )
    vector_request, skip_reason = build_vector_request(
        query_case=query_case,
        field=str(scenario_knn.get("field") or vector_cfg.field),
        top_k=int(scenario_knn.get("k") or candidate_pool),
        rows=candidate_pool,
    )
    if vector_request is None:
        return {
            "docs": [],
            "raw_response_meta": {},
            "subscores": [],
            "error": None,
            "skipped": True,
            "skip_reason": skip_reason,
            "request_mode": "client_blend",
            "raw_request": {
                "lexical": lexical_request,
                "vector": None,
            },
        }

    lexical_docs, lexical_meta, lexical_error = _execute_request(
        client=client,
        collection=collection,
        request=lexical_request,
        limit=candidate_pool,
    )
    vector_docs, vector_meta, vector_error = _execute_request(
        client=client,
        collection=collection,
        request=vector_request,
        limit=candidate_pool,
    )

    if lexical_error or vector_error:
        return {
            "docs": [],
            "raw_response_meta": {
                "lexical": lexical_meta,
                "vector": vector_meta,
            },
            "subscores": [],
            "error": "; ".join(
                part
                for part in (
                    f"lexical_error={lexical_error}" if lexical_error else "",
                    f"vector_error={vector_error}" if vector_error else "",
                )
                if part
            ),
            "skipped": False,
            "skip_reason": None,
            "request_mode": "client_blend",
            "raw_request": {
                "lexical": lexical_request,
                "vector": vector_request,
            },
        }

    ranked = blend_rankings(
        lexical_docs=lexical_docs,
        vector_docs=vector_docs,
        method=str(scenario_blend.get("method", "linear")),
        top_k=top_k,
        candidate_pool=candidate_pool,
        weight_lexical=float(scenario_blend.get("weight_lexical", 0.7)),
        weight_vector=float(scenario_blend.get("weight_vector", 0.3)),
        normalize=str(scenario_blend.get("normalize", "none")),
        missing_vector_score=float(scenario_blend.get("missing_vector_score", 0.0)),
        missing_lexical_score=float(scenario_blend.get("missing_lexical_score", 0.0)),
        rrf_k=int(scenario_blend.get("rrf_k", 60)),
    )

    return {
        "docs": [
            {
                "id": item["id"],
                "score": item.get("score"),
                "rank": item.get("rank"),
            }
            for item in ranked
        ],
        "raw_response_meta": {
            "status": 0,
            "QTime": (lexical_meta.get("QTime") or 0) + (vector_meta.get("QTime") or 0),
            "numFound": max(
                int(lexical_meta.get("numFound") or 0),
                int(vector_meta.get("numFound") or 0),
            ),
            "elapsed_ms": round(
                float(lexical_meta.get("elapsed_ms") or 0.0)
                + float(vector_meta.get("elapsed_ms") or 0.0),
                3,
            ),
            "blend_execution": "client",
            "lexical_meta": lexical_meta,
            "vector_meta": vector_meta,
        },
        "subscores": [
            {
                "id": item["id"],
                "lexical_component": item.get("lexical_component"),
                "vector_component": item.get("vector_component"),
                "lexical_score": item.get("lexical_score"),
                "vector_score": item.get("vector_score"),
            }
            for item in ranked
        ],
        "error": None,
        "skipped": False,
        "skip_reason": None,
        "request_mode": "client_blend",
        "raw_request": {
            "lexical": lexical_request,
            "vector": vector_request,
        },
        "blend_inputs": {
            "lexical_docs": lexical_docs,
            "vector_docs": vector_docs,
            "blend": scenario_blend,
            "candidate_pool": candidate_pool,
            "top_k": top_k,
        },
    }


def _run_scenario_target(
    *,
    client: Any,
    collection: str,
    query_case: QueryCase,
    scenario: VectorScenario,
    vector_cfg: VectorRuntimeConfig,
    request_defaults: dict[str, Any],
    top_k: int,
    candidate_pool: int,
) -> dict[str, Any]:
    mode = scenario.mode

    if mode == "lexical_only":
        request = build_lexical_request(
            query_case=query_case,
            rows=top_k,
            base_defaults=request_defaults,
            lexical_overrides=scenario.lexical,
        )
        docs, meta, error = _execute_request(
            client=client,
            collection=collection,
            request=request,
            limit=top_k,
        )
        return {
            "docs": docs,
            "raw_response_meta": meta,
            "subscores": [],
            "error": error,
            "skipped": False,
            "skip_reason": None,
            "request_mode": str(request.get("mode")),
            "raw_request": request,
        }

    if mode == "vector_only":
        knn = scenario.knn if isinstance(scenario.knn, dict) else {}
        request, skip_reason = build_vector_request(
            query_case=query_case,
            field=str(knn.get("field") or vector_cfg.field),
            top_k=int(knn.get("k") or candidate_pool),
            rows=int(knn.get("topK") or top_k),
        )
        if request is None:
            return {
                "docs": [],
                "raw_response_meta": {},
                "subscores": [],
                "error": None,
                "skipped": True,
                "skip_reason": skip_reason,
                "request_mode": "params",
                "raw_request": None,
            }
        docs, meta, error = _execute_request(
            client=client,
            collection=collection,
            request=request,
            limit=top_k,
        )
        return {
            "docs": docs,
            "raw_response_meta": meta,
            "subscores": [],
            "error": error,
            "skipped": False,
            "skip_reason": None,
            "request_mode": str(request.get("mode")),
            "raw_request": request,
        }

    scenario_blend = scenario.blend if isinstance(scenario.blend, dict) else {}
    execution = str(scenario_blend.get("execution", "auto"))
    if execution in {"auto", "solr_native"} and detect_native_hybrid_request(query_case):
        request = build_lexical_request(
            query_case=query_case,
            rows=top_k,
            base_defaults=request_defaults,
            lexical_overrides=scenario.lexical,
        )
        docs, meta, error = _execute_request(
            client=client,
            collection=collection,
            request=request,
            limit=top_k,
        )
        if not error:
            meta["blend_execution"] = "solr_native"
        return {
            "docs": docs,
            "raw_response_meta": meta,
            "subscores": [],
            "error": error,
            "skipped": False,
            "skip_reason": None,
            "request_mode": str(request.get("mode")),
            "raw_request": request,
        }

    return _run_hybrid_client(
        client=client,
        collection=collection,
        query_case=query_case,
        scenario=scenario,
        vector_cfg=vector_cfg,
        request_defaults=request_defaults,
        top_k=top_k,
        candidate_pool=candidate_pool,
    )


def run_vector_scenarios(
    *,
    baseline_client: Any,
    baseline_collection: str,
    shadow_client: Any,
    shadow_collection: str,
    queries: list[QueryCase],
    request_defaults: dict[str, Any],
    vector_cfg: VectorRuntimeConfig,
) -> dict[str, Any]:
    request_defaults = _flatten_defaults(request_defaults)
    eval_cfg = vector_cfg.evaluation if isinstance(vector_cfg.evaluation, dict) else {}
    top_k = int(eval_cfg.get("topK", 10))
    candidate_pool = int(eval_cfg.get("candidate_pool", max(100, top_k)))

    scenario_results: dict[str, Any] = {}
    for scenario in vector_cfg.scenarios:
        pairs: list[dict[str, Any]] = []
        failures = 0
        skips = 0

        for case in queries:
            baseline_result = _run_scenario_target(
                client=baseline_client,
                collection=baseline_collection,
                query_case=case,
                scenario=scenario,
                vector_cfg=vector_cfg,
                request_defaults=request_defaults,
                top_k=top_k,
                candidate_pool=candidate_pool,
            )
            shadow_result = _run_scenario_target(
                client=shadow_client,
                collection=shadow_collection,
                query_case=case,
                scenario=scenario,
                vector_cfg=vector_cfg,
                request_defaults=request_defaults,
                top_k=top_k,
                candidate_pool=candidate_pool,
            )

            if baseline_result.get("error"):
                failures += 1
            if shadow_result.get("error"):
                failures += 1
            if baseline_result.get("skipped") or shadow_result.get("skipped"):
                skips += 1

            pairs.append(
                {
                    "query": case.to_dict(),
                    "baseline": baseline_result,
                    "shadow": shadow_result,
                }
            )

        scenario_results[scenario.name] = {
            "scenario": scenario.to_dict(),
            "k": top_k,
            "candidate_pool": candidate_pool,
            "pairs": pairs,
            "stats": {
                "queries_total": len(queries),
                "failures": failures,
                "skips": skips,
            },
        }

    return {
        "enabled": True,
        "vector": {
            "field": vector_cfg.field,
            "dimension": vector_cfg.dimension,
            "similarity": vector_cfg.similarity,
            "query_vector_policy": vector_cfg.query_vector_policy,
        },
        "evaluation": eval_cfg,
        "scenario_results": scenario_results,
    }
