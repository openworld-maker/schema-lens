"""Hybrid blending functions for lexical and vector candidate rankings."""

from __future__ import annotations

from math import sqrt
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_map(docs: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in docs:
        doc_id = item.get("id")
        if doc_id is None:
            continue
        out[str(doc_id)] = _safe_float(item.get("score"), 0.0)
    return out


def _rank_map(docs: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for idx, item in enumerate(docs, start=1):
        doc_id = item.get("id")
        if doc_id is None:
            continue
        out[str(doc_id)] = idx
    return out


def _normalize(values: dict[str, float], method: str) -> dict[str, float]:
    if method == "none" or not values:
        return dict(values)

    score_values = list(values.values())
    if method == "minmax":
        lo = min(score_values)
        hi = max(score_values)
        if hi == lo:
            return {doc_id: 1.0 for doc_id in values}
        return {doc_id: (score - lo) / (hi - lo) for doc_id, score in values.items()}

    if method == "zscore":
        mean = sum(score_values) / len(score_values)
        variance = sum((score - mean) ** 2 for score in score_values) / len(score_values)
        std = sqrt(variance)
        if std == 0.0:
            return {doc_id: 1.0 for doc_id in values}
        return {doc_id: (score - mean) / std for doc_id, score in values.items()}

    return dict(values)


def _to_ranked_docs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        item["rank"] = idx
        ranked.append(item)
    return ranked


def blend_rankings(
    *,
    lexical_docs: list[dict[str, Any]],
    vector_docs: list[dict[str, Any]],
    method: str,
    top_k: int,
    candidate_pool: int,
    weight_lexical: float,
    weight_vector: float,
    normalize: str,
    missing_vector_score: float,
    missing_lexical_score: float,
    rrf_k: int,
) -> list[dict[str, Any]]:
    lexical_docs = lexical_docs[:candidate_pool]
    vector_docs = vector_docs[:candidate_pool]

    l_score = _score_map(lexical_docs)
    v_score = _score_map(vector_docs)
    l_rank = _rank_map(lexical_docs)
    v_rank = _rank_map(vector_docs)

    candidates = sorted(set(l_score.keys()) | set(v_score.keys()))

    if method == "rrf":
        rows: list[dict[str, Any]] = []
        for doc_id in candidates:
            l_part = 0.0
            v_part = 0.0
            if doc_id in l_rank:
                l_part = weight_lexical / (rrf_k + l_rank[doc_id])
            if doc_id in v_rank:
                v_part = weight_vector / (rrf_k + v_rank[doc_id])
            rows.append(
                {
                    "id": doc_id,
                    "score": l_part + v_part,
                    "lexical_score": l_score.get(doc_id),
                    "vector_score": v_score.get(doc_id),
                    "lexical_component": l_part,
                    "vector_component": v_part,
                }
            )
        rows.sort(key=lambda row: row["score"], reverse=True)
        return _to_ranked_docs(rows[:top_k])

    normalized_l = _normalize(l_score, normalize if method == "normalize_linear" else "none")
    normalized_v = _normalize(v_score, normalize if method == "normalize_linear" else "none")

    rows = []
    for doc_id in candidates:
        l_val = normalized_l.get(doc_id, missing_lexical_score)
        v_val = normalized_v.get(doc_id, missing_vector_score)
        l_component = weight_lexical * l_val
        v_component = weight_vector * v_val
        rows.append(
            {
                "id": doc_id,
                "score": l_component + v_component,
                "lexical_score": l_score.get(doc_id),
                "vector_score": v_score.get(doc_id),
                "lexical_component": l_component,
                "vector_component": v_component,
            }
        )

    rows.sort(key=lambda row: row["score"], reverse=True)
    return _to_ranked_docs(rows[:top_k])
