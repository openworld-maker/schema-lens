"""Replay diff computation."""

from __future__ import annotations

from typing import Any

from schema_lens.compare.metrics import jaccard_at_k, kendall_tau_at_k, overlap_at_k


def _risk_for(overlap: int, tau: float | None, k: int) -> tuple[str, list[str]]:
    flags: list[str] = []
    tau_value = tau if tau is not None else 0.0
    high_overlap_threshold = k * 0.6
    medium_overlap_threshold = k * 0.8

    if overlap < high_overlap_threshold or tau_value < 0.2:
        severity = "HIGH"
    elif overlap < medium_overlap_threshold:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    if overlap < high_overlap_threshold:
        flags.append("LOW_OVERLAP")
    if tau is not None and tau < 0.2:
        flags.append("LOW_TAU")
    flags.insert(0, severity)
    return severity, flags


def _doc_scores(doc_list: list[dict[str, Any]]) -> dict[str, float | None]:
    return {str(doc["id"]): doc.get("score") for doc in doc_list if "id" in doc}


def compare_replay(replay_data: dict[str, Any], k: int) -> dict[str, Any]:
    diffs: list[dict[str, Any]] = []

    for pair in replay_data.get("pairs", []):
        query = pair.get("query", {})
        baseline = pair.get("baseline", {})
        shadow = pair.get("shadow", {})

        baseline_error = baseline.get("error")
        shadow_error = shadow.get("error")

        base_docs = baseline.get("docs", [])
        shadow_docs = shadow.get("docs", [])

        base_ids = [str(doc["id"]) for doc in base_docs if "id" in doc][:k]
        shadow_ids = [str(doc["id"]) for doc in shadow_docs if "id" in doc][:k]

        overlap = overlap_at_k(base_ids, shadow_ids)
        jaccard = jaccard_at_k(base_ids, shadow_ids)
        tau = kendall_tau_at_k(base_ids, shadow_ids)

        rank_b = {doc_id: idx + 1 for idx, doc_id in enumerate(base_ids)}
        rank_s = {doc_id: idx + 1 for idx, doc_id in enumerate(shadow_ids)}
        common = sorted(
            set(base_ids) & set(shadow_ids),
            key=lambda x: abs(rank_s[x] - rank_b[x]),
            reverse=True,
        )

        moved_docs = [
            {
                "id": doc_id,
                "rank_baseline": rank_b[doc_id],
                "rank_shadow": rank_s[doc_id],
                "delta": rank_s[doc_id] - rank_b[doc_id],
            }
            for doc_id in common
            if rank_s[doc_id] != rank_b[doc_id]
        ]

        dropped_docs = [doc_id for doc_id in base_ids if doc_id not in rank_s]
        new_docs = [doc_id for doc_id in shadow_ids if doc_id not in rank_b]

        scores_b = _doc_scores(base_docs)
        scores_s = _doc_scores(shadow_docs)
        score_deltas = []
        for doc_id in sorted(set(base_ids) & set(shadow_ids)):
            score_deltas.append(
                {
                    "id": doc_id,
                    "score_base": scores_b.get(doc_id),
                    "score_shadow": scores_s.get(doc_id),
                    "delta": None
                    if scores_b.get(doc_id) is None or scores_s.get(doc_id) is None
                    else scores_s.get(doc_id) - scores_b.get(doc_id),
                }
            )

        severity, flags = _risk_for(overlap, tau, k)
        if baseline_error or shadow_error:
            severity = "HIGH"
            if baseline_error:
                flags.append("BASELINE_QUERY_ERROR")
            if shadow_error:
                flags.append("SHADOW_QUERY_ERROR")

        diffs.append(
            {
                "query_id": query.get("id"),
                "raw_line": query.get("raw_line"),
                "params": query.get("params", {}),
                "topk_overlap_count": overlap,
                "jaccard": jaccard,
                "kendall_tau": tau,
                "moved_docs": moved_docs,
                "dropped_docs": dropped_docs,
                "new_docs": new_docs,
                "score_deltas": score_deltas,
                "risk_flags": flags,
                "risk_severity": severity,
                "errors": {
                    "baseline": baseline_error,
                    "shadow": shadow_error,
                },
            }
        )

    total = len(diffs)
    high = len([d for d in diffs if d.get("risk_severity") == "HIGH"])
    avg_overlap = (
        sum(d.get("topk_overlap_count", 0) for d in diffs) / total if total else 0.0
    )

    ranked = sorted(
        diffs,
        key=lambda d: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(d.get("risk_severity"), 3),
            d.get("topk_overlap_count", k),
            1.0 if d.get("kendall_tau") is None else d.get("kendall_tau"),
        ),
    )

    return {
        "k": k,
        "summary": {
            "queries_total": total,
            "avg_overlap": avg_overlap,
            "high_risk_percent": (high / total * 100.0) if total else 0.0,
        },
        "top_regressions": ranked[:20],
        "diffs": diffs,
    }
