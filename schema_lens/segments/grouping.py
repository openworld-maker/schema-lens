"""Per-segment aggregation over compare diffs."""

from __future__ import annotations

from typing import Any

from schema_lens.segments.model import normalize_segment


def aggregate_by_segment(
    diffs: list[dict[str, Any]],
    *,
    segment_keys: list[str] | None = None,
) -> dict[str, Any]:
    keys = segment_keys or ["tenant", "region", "locale", "catalog"]
    by_segment: dict[str, dict[str, Any]] = {}

    for diff in diffs:
        segment = normalize_segment(diff.get("segment") if isinstance(diff, dict) else None)
        if not segment:
            segment = {"segment": "unlabeled"}

        for key in keys:
            if key not in segment:
                continue
            label = f"{key}:{segment[key]}"
            bucket = by_segment.setdefault(
                label,
                {
                    "segment_key": key,
                    "segment_value": segment[key],
                    "queries_total": 0,
                    "high_risk_queries": 0,
                    "avg_overlap_ratio": 0.0,
                },
            )
            bucket["queries_total"] += 1
            if diff.get("risk_severity") == "HIGH":
                bucket["high_risk_queries"] += 1
            bucket["avg_overlap_ratio"] += float(diff.get("overlap_ratio", 0.0) or 0.0)

    for bucket in by_segment.values():
        total = int(bucket["queries_total"])
        bucket["high_risk_percent"] = (bucket["high_risk_queries"] / total * 100.0) if total else 0.0
        bucket["avg_overlap_ratio"] = (bucket["avg_overlap_ratio"] / total) if total else 0.0

    top_impacted = sorted(
        by_segment.values(),
        key=lambda row: (-(row.get("high_risk_percent", 0.0)), row.get("avg_overlap_ratio", 1.0)),
    )[:20]

    return {
        "enabled": True,
        "by_segment": by_segment,
        "top_impacted": top_impacted,
    }
