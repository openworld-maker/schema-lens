"""LTR report helpers."""

from __future__ import annotations

from typing import Any


def summarize_ltr_impact(payload: dict[str, Any]) -> list[str]:
    if not payload.get("enabled"):
        return []
    return [
        f"LTR queries analyzed: {payload.get('queries_analyzed', 0)}",
        f"Feature drifts found: {payload.get('feature_drift_count', 0)}",
    ]
