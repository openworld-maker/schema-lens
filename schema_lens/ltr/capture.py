"""LTR capture for replay pairs."""

from __future__ import annotations

from typing import Any

from schema_lens.ltr.detect import detect_ltr_params
from schema_lens.ltr.diff import diff_feature_maps, parse_feature_string


def _doc_feature_map(docs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for doc in docs:
        if not isinstance(doc, dict) or "id" not in doc:
            continue
        for feature_field in ("[features]", "features"):
            raw = doc.get(feature_field)
            if isinstance(raw, str):
                out[str(doc["id"])] = parse_feature_string(raw)
                break
    return out


def capture_ltr_impact(replay_data: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for pair in replay_data.get("pairs", []):
        if not isinstance(pair, dict):
            continue
        params = pair.get("effective_params", {})
        if not detect_ltr_params(params if isinstance(params, dict) else {}):
            continue
        baseline_docs = pair.get("baseline", {}).get("docs", [])
        shadow_docs = pair.get("shadow", {}).get("docs", [])
        base_map = _doc_feature_map(baseline_docs if isinstance(baseline_docs, list) else [])
        shadow_map = _doc_feature_map(shadow_docs if isinstance(shadow_docs, list) else [])
        doc_ids = sorted(set(base_map.keys()) | set(shadow_map.keys()))
        for doc_id in doc_ids:
            rows.append(
                {
                    "query_id": pair.get("query", {}).get("id"),
                    "doc_id": doc_id,
                    "feature_deltas": diff_feature_maps(
                        base_map.get(doc_id, {}),
                        shadow_map.get(doc_id, {}),
                    ),
                }
            )

    return {
        "enabled": bool(rows),
        "queries_analyzed": len(
            {
                row.get("query_id")
                for row in rows
                if row.get("query_id") is not None
            }
        ),
        "feature_drift_count": len(
            [row for row in rows if row.get("feature_deltas")]
        ),
        "rows": rows,
        "reason": None if rows else "No LTR params or feature logs detected.",
    }
