"""Compare vector/hybrid scenario replay outputs."""

from __future__ import annotations

from typing import Any

from schema_lens.compare.metrics import jaccard_at_k, kendall_tau_at_k, overlap_at_k


def _ids(result: dict[str, Any], k: int) -> list[str]:
    docs = result.get("docs", [])
    if not isinstance(docs, list):
        return []
    out = []
    for row in docs:
        if not isinstance(row, dict) or "id" not in row:
            continue
        out.append(str(row["id"]))
        if len(out) >= k:
            break
    return out


def _score_map(result: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    docs = result.get("docs", [])
    if not isinstance(docs, list):
        return out
    for row in docs:
        if not isinstance(row, dict) or "id" not in row:
            continue
        out[str(row["id"])] = row.get("score")
    return out


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _confidence(overlap_hl: int, overlap_hv: int, k: int) -> str:
    denom = overlap_hl + overlap_hv
    gap = abs(overlap_hl - overlap_hv)
    if denom >= max(6, int(0.6 * k)) and gap >= 2:
        return "HIGH"
    if denom >= max(4, int(0.4 * k)):
        return "MEDIUM"
    return "LOW"


def _dominance(overlap_hl: int, overlap_hv: int) -> str:
    if overlap_hl - overlap_hv >= 2:
        return "lexical_dominant"
    if overlap_hv - overlap_hl >= 2:
        return "vector_dominant"
    return "balanced"


def _contribution(overlap_hl: int, overlap_hv: int) -> tuple[float, float]:
    denom = overlap_hl + overlap_hv
    if denom <= 0:
        return 0.5, 0.5
    return overlap_hl / denom, overlap_hv / denom


def compare_vector_hybrid(
    *,
    scenario_replay: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    scenario_results = scenario_replay.get("scenario_results", {})
    if not isinstance(scenario_results, dict) or not scenario_results:
        return {
            "enabled": False,
            "scenario_summaries": [],
            "scenario_pair_diffs": {},
            "hybrid_contribution": {},
            "semantic_churn": {},
            "narratives": [],
        }

    lexical_anchor_name = None
    vector_anchor_name = None
    for name, payload in scenario_results.items():
        scenario = payload.get("scenario", {}) if isinstance(payload, dict) else {}
        mode = scenario.get("mode")
        if mode == "lexical_only" and lexical_anchor_name is None:
            lexical_anchor_name = name
        if mode == "vector_only" and vector_anchor_name is None:
            vector_anchor_name = name

    summaries: list[dict[str, Any]] = []
    scenario_pair_diffs: dict[str, Any] = {}
    hybrid_contribution: dict[str, Any] = {}
    semantic_churn: dict[str, Any] = {}

    for scenario_name, payload in scenario_results.items():
        if not isinstance(payload, dict):
            continue
        scenario = payload.get("scenario", {})
        mode = str(scenario.get("mode", ""))
        pairs = payload.get("pairs", [])
        if not isinstance(pairs, list):
            pairs = []

        per_query: list[dict[str, Any]] = []
        overlaps: list[float] = []
        jaccards: list[float] = []
        taus: list[float] = []
        qtimes: list[float] = []
        top1_changed = 0
        top10_changed_gt_50 = 0
        valid_pair_count = 0

        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            query = pair.get("query", {}) if isinstance(pair.get("query"), dict) else {}
            baseline = pair.get("baseline", {}) if isinstance(pair.get("baseline"), dict) else {}
            shadow = pair.get("shadow", {}) if isinstance(pair.get("shadow"), dict) else {}

            skipped = bool(baseline.get("skipped") or shadow.get("skipped"))
            skip_reason = baseline.get("skip_reason") or shadow.get("skip_reason")

            base_ids = _ids(baseline, top_k)
            shadow_ids = _ids(shadow, top_k)

            overlap = overlap_at_k(base_ids, shadow_ids)
            jaccard = jaccard_at_k(base_ids, shadow_ids)
            tau = kendall_tau_at_k(base_ids, shadow_ids)
            score_deltas = []
            scores_b = _score_map(baseline)
            scores_s = _score_map(shadow)
            for doc_id in sorted(set(base_ids) & set(shadow_ids)):
                base_score = scores_b.get(doc_id)
                shadow_score = scores_s.get(doc_id)
                delta = None
                if base_score is not None and shadow_score is not None:
                    try:
                        delta = float(shadow_score) - float(base_score)
                    except (TypeError, ValueError):
                        delta = None
                score_deltas.append(
                    {
                        "id": doc_id,
                        "score_baseline": base_score,
                        "score_shadow": shadow_score,
                        "delta": delta,
                    }
                )

            if not skipped:
                valid_pair_count += 1
                overlaps.append(overlap / top_k if top_k else 0.0)
                jaccards.append(jaccard)
                if tau is not None:
                    taus.append(tau)
                for meta in (
                    baseline.get("raw_response_meta", {}),
                    shadow.get("raw_response_meta", {}),
                ):
                    if isinstance(meta, dict) and meta.get("QTime") is not None:
                        try:
                            qtimes.append(float(meta.get("QTime")))
                        except (TypeError, ValueError):
                            pass

                if mode == "vector_only":
                    if base_ids[:1] != shadow_ids[:1]:
                        top1_changed += 1
                    if top_k > 0 and overlap / top_k < 0.5:
                        top10_changed_gt_50 += 1

            per_query.append(
                {
                    "query_id": query.get("id"),
                    "query_name": query.get("name") or query.get("raw_line"),
                    "baseline_topk_ids": base_ids,
                    "shadow_topk_ids": shadow_ids,
                    "overlap": overlap,
                    "jaccard": jaccard,
                    "kendall_tau": tau,
                    "score_deltas": score_deltas,
                    "numFound_baseline": baseline.get("raw_response_meta", {}).get("numFound"),
                    "numFound_shadow": shadow.get("raw_response_meta", {}).get("numFound"),
                    "QTime_baseline": baseline.get("raw_response_meta", {}).get("QTime"),
                    "QTime_shadow": shadow.get("raw_response_meta", {}).get("QTime"),
                    "skipped": skipped,
                    "skip_reason": skip_reason,
                    "errors": {
                        "baseline": baseline.get("error"),
                        "shadow": shadow.get("error"),
                    },
                }
            )

        scenario_pair_diffs[scenario_name] = per_query
        summaries.append(
            {
                "scenario_name": scenario_name,
                "mode": mode,
                "avg_overlap_ratio": _avg(overlaps),
                "avg_jaccard": _avg(jaccards),
                "avg_kendall_tau": _avg(taus),
                "avg_qtime": _avg(qtimes),
                "queries": len(pairs),
                "valid_queries": valid_pair_count,
            }
        )

        if mode == "vector_only":
            denom = valid_pair_count or 1
            semantic_churn[scenario_name] = {
                "top1_changed_percent": (top1_changed / denom) * 100.0,
                "queries_top10_changed_gt_50_percent": (top10_changed_gt_50 / denom) * 100.0,
            }

    # Hybrid contribution estimates against lexical/vector anchors (shadow target)
    if lexical_anchor_name and vector_anchor_name:
        lexical_pairs = {
            pair.get("query", {}).get("id"): pair
            for pair in scenario_results.get(lexical_anchor_name, {}).get("pairs", [])
            if isinstance(pair, dict)
        }
        vector_pairs = {
            pair.get("query", {}).get("id"): pair
            for pair in scenario_results.get(vector_anchor_name, {}).get("pairs", [])
            if isinstance(pair, dict)
        }

        for scenario_name, payload in scenario_results.items():
            scenario = payload.get("scenario", {}) if isinstance(payload, dict) else {}
            if str(scenario.get("mode")) != "hybrid":
                continue
            rows: list[dict[str, Any]] = []
            counts = {
                "lexical_dominant": 0,
                "vector_dominant": 0,
                "balanced": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }
            l_est_values: list[float] = []
            v_est_values: list[float] = []

            pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                query = pair.get("query", {}) if isinstance(pair.get("query"), dict) else {}
                qid = query.get("id")
                hybrid_shadow_ids = _ids(pair.get("shadow", {}), top_k)

                lexical_shadow_ids = _ids(
                    lexical_pairs.get(qid, {}).get("shadow", {}),
                    top_k,
                )
                vector_shadow_ids = _ids(
                    vector_pairs.get(qid, {}).get("shadow", {}),
                    top_k,
                )

                if not hybrid_shadow_ids or not lexical_shadow_ids or not vector_shadow_ids:
                    continue

                overlap_hl = overlap_at_k(hybrid_shadow_ids, lexical_shadow_ids)
                overlap_hv = overlap_at_k(hybrid_shadow_ids, vector_shadow_ids)
                dominance = _dominance(overlap_hl, overlap_hv)
                l_est, v_est = _contribution(overlap_hl, overlap_hv)
                confidence = _confidence(overlap_hl, overlap_hv, top_k)

                counts[dominance] += 1
                counts[confidence.lower()] += 1
                l_est_values.append(l_est)
                v_est_values.append(v_est)

                rows.append(
                    {
                        "query_id": qid,
                        "query_name": query.get("name") or query.get("raw_line"),
                        "hybrid_topk_ids": hybrid_shadow_ids,
                        "lexical_anchor_topk_ids": lexical_shadow_ids,
                        "vector_anchor_topk_ids": vector_shadow_ids,
                        "overlap_hybrid_lexical": overlap_hl,
                        "overlap_hybrid_vector": overlap_hv,
                        "dominance": dominance,
                        "contribution_lexical_estimate": l_est,
                        "contribution_vector_estimate": v_est,
                        "confidence": confidence,
                    }
                )

            hybrid_contribution[scenario_name] = {
                "per_query": rows,
                "summary": {
                    "queries": len(rows),
                    "avg_contribution_lexical_estimate": _avg(l_est_values),
                    "avg_contribution_vector_estimate": _avg(v_est_values),
                    "lexical_dominant_percent": (
                        counts["lexical_dominant"] / len(rows) * 100.0 if rows else 0.0
                    ),
                    "vector_dominant_percent": (
                        counts["vector_dominant"] / len(rows) * 100.0 if rows else 0.0
                    ),
                    "balanced_percent": (
                        counts["balanced"] / len(rows) * 100.0 if rows else 0.0
                    ),
                    "confidence_distribution": {
                        "HIGH": counts["high"],
                        "MEDIUM": counts["medium"],
                        "LOW": counts["low"],
                    },
                },
            }

    narratives: list[str] = []
    for scenario_name, payload in hybrid_contribution.items():
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        l_est = float(summary.get("avg_contribution_lexical_estimate", 0.0))
        v_est = float(summary.get("avg_contribution_vector_estimate", 0.0))
        if v_est > l_est:
            narratives.append(
                f"Scenario '{scenario_name}': vector similarity now dominates "
                f"({l_est:.2f} lexical vs {v_est:.2f} vector contribution estimate)."
            )
        else:
            narratives.append(
                f"Scenario '{scenario_name}': lexical signals remain stronger "
                f"({l_est:.2f} lexical vs {v_est:.2f} vector contribution estimate)."
            )

    return {
        "enabled": True,
        "comparison_mode": "lexical_anchor",
        "topK": top_k,
        "scenario_summaries": summaries,
        "scenario_pair_diffs": scenario_pair_diffs,
        "hybrid_contribution": hybrid_contribution,
        "semantic_churn": semantic_churn,
        "narratives": narratives,
        "anchor_scenarios": {
            "lexical": lexical_anchor_name,
            "vector": vector_anchor_name,
        },
    }
