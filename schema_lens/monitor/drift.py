"""Drift calculations over baseline vs current results."""

from __future__ import annotations

from typing import Any


def compute_drift_summary(
    baseline_report: dict[str, Any] | None,
    current_report: dict[str, Any] | None,
) -> dict[str, Any]:
    baseline_summary = (
        baseline_report.get("summary", {}) if isinstance(baseline_report, dict) else {}
    )
    current_summary = current_report.get("summary", {}) if isinstance(current_report, dict) else {}
    out: dict[str, Any] = {}
    for key in (
        "avg_overlap",
        "high_risk_percent",
        "avg_numfound_delta",
        "avg_sort_instability_ratio",
    ):
        base = baseline_summary.get(key)
        current = current_summary.get(key)
        if isinstance(base, (int, float)) and isinstance(current, (int, float)):
            out[key] = {
                "baseline": float(base),
                "current": float(current),
                "delta": float(current) - float(base),
            }
    return out
