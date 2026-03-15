"""Hybrid blend weight sensitivity analysis."""

from __future__ import annotations

from typing import Any

from schema_lens.compare.metrics import overlap_at_k
from schema_lens.vector.blend import blend_rankings


def _ids(rows: list[dict[str, Any]], top_k: int) -> list[str]:
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or "id" not in row:
            continue
        out.append(str(row["id"]))
        if len(out) >= top_k:
            break
    return out


def run_hybrid_sensitivity(
    *,
    scenario_replay: dict[str, Any],
    weights: list[float],
    top_k: int,
    candidate_pool: int,
) -> dict[str, Any]:
    scenario_results = scenario_replay.get("scenario_results", {})
    if not isinstance(scenario_results, dict) or not scenario_results:
        return {"enabled": False, "weights": weights, "scenarios": []}

    scenarios_payload: list[dict[str, Any]] = []
    sorted_weights = sorted(float(weight) for weight in weights)

    for scenario_name, payload in scenario_results.items():
        if not isinstance(payload, dict):
            continue
        scenario = payload.get("scenario", {})
        if str(scenario.get("mode")) != "hybrid":
            continue

        blend_cfg = scenario.get("blend", {}) if isinstance(scenario.get("blend"), dict) else {}
        method = str(blend_cfg.get("method", "linear"))
        normalize = str(blend_cfg.get("normalize", "none"))
        rrf_k = int(blend_cfg.get("rrf_k", 60))
        missing_vector_score = float(blend_cfg.get("missing_vector_score", 0.0))
        missing_lexical_score = float(blend_cfg.get("missing_lexical_score", 0.0))

        query_summaries: list[dict[str, Any]] = []
        top1_flip_queries = 0

        pairs = payload.get("pairs", [])
        if not isinstance(pairs, list):
            pairs = []
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            query = pair.get("query", {}) if isinstance(pair.get("query"), dict) else {}
            shadow = pair.get("shadow", {}) if isinstance(pair.get("shadow"), dict) else {}
            blend_inputs = shadow.get("blend_inputs")
            if not isinstance(blend_inputs, dict):
                continue
            lexical_docs = blend_inputs.get("lexical_docs", [])
            vector_docs = blend_inputs.get("vector_docs", [])
            if not isinstance(lexical_docs, list) or not isinstance(vector_docs, list):
                continue

            progression: list[dict[str, Any]] = []
            previous_top_ids: list[str] | None = None
            previous_weight: float | None = None
            previous_top1: str | None = None
            top1_tipping_point: dict[str, Any] | None = None
            topk_tipping_point: dict[str, Any] | None = None

            for weight_vector in sorted_weights:
                weight_lexical = 1.0 - weight_vector
                ranked = blend_rankings(
                    lexical_docs=lexical_docs,
                    vector_docs=vector_docs,
                    method=method,
                    top_k=top_k,
                    candidate_pool=candidate_pool,
                    weight_lexical=weight_lexical,
                    weight_vector=weight_vector,
                    normalize=normalize,
                    missing_vector_score=missing_vector_score,
                    missing_lexical_score=missing_lexical_score,
                    rrf_k=rrf_k,
                )
                top_ids = _ids(ranked, top_k)
                top1 = top_ids[0] if top_ids else None
                progression.append(
                    {
                        "weight_vector": weight_vector,
                        "weight_lexical": weight_lexical,
                        "top1": top1,
                        "topk_ids": top_ids,
                    }
                )

                if previous_top_ids is not None and previous_weight is not None:
                    overlap = overlap_at_k(previous_top_ids, top_ids)
                    churn_ratio = 1.0 - (overlap / top_k if top_k else 0.0)
                    entered = [doc_id for doc_id in top_ids if doc_id not in previous_top_ids]
                    left = [doc_id for doc_id in previous_top_ids if doc_id not in top_ids]
                    if top1_tipping_point is None and previous_top1 != top1:
                        top1_tipping_point = {
                            "from_weight_vector": previous_weight,
                            "to_weight_vector": weight_vector,
                            "from_top1": previous_top1,
                            "to_top1": top1,
                        }
                    if topk_tipping_point is None and churn_ratio > 0.30:
                        topk_tipping_point = {
                            "from_weight_vector": previous_weight,
                            "to_weight_vector": weight_vector,
                            "churn_ratio": churn_ratio,
                            "entered": entered,
                            "left": left,
                        }

                previous_top_ids = top_ids
                previous_weight = weight_vector
                previous_top1 = top1

            if top1_tipping_point is not None:
                top1_flip_queries += 1

            query_summaries.append(
                {
                    "query_id": query.get("id"),
                    "query_name": query.get("name") or query.get("raw_line"),
                    "top1_progression": [
                        {
                            "weight_vector": row["weight_vector"],
                            "top1": row["top1"],
                        }
                        for row in progression
                    ],
                    "top1_tipping_point": top1_tipping_point,
                    "topk_tipping_point": topk_tipping_point,
                    "steps": progression,
                }
            )

        scenarios_payload.append(
            {
                "scenario_name": scenario_name,
                "queries": len(query_summaries),
                "queries_with_top1_flip": top1_flip_queries,
                "top1_flip_percent": (
                    (top1_flip_queries / len(query_summaries) * 100.0) if query_summaries else 0.0
                ),
                "query_summaries": query_summaries,
            }
        )

    return {
        "enabled": bool(scenarios_payload),
        "weights": sorted_weights,
        "scenarios": scenarios_payload,
    }
