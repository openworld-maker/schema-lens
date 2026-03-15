"""Post-cutover verification helpers."""

from __future__ import annotations

from typing import Any


def verify_post_cutover(
    *,
    canary_compare: dict[str, Any],
    prod_compare: dict[str, Any],
    overlap_threshold: float = 0.7,
    high_risk_threshold_pct: float = 5.0,
) -> dict[str, Any]:
    canary_summary = canary_compare.get("summary", {}) if isinstance(canary_compare, dict) else {}
    prod_summary = prod_compare.get("summary", {}) if isinstance(prod_compare, dict) else {}

    canary_overlap = float(canary_summary.get("avg_overlap_ratio", canary_summary.get("avg_overlap", 0.0)))
    prod_overlap = float(prod_summary.get("avg_overlap_ratio", prod_summary.get("avg_overlap", 0.0)))
    prod_high_risk = float(prod_summary.get("high_risk_percent", 0.0))

    checks = {
        "overlap_ok": canary_overlap >= overlap_threshold and prod_overlap >= overlap_threshold,
        "high_risk_ok": prod_high_risk <= high_risk_threshold_pct,
    }
    return {
        "overlap_threshold": overlap_threshold,
        "high_risk_threshold_pct": high_risk_threshold_pct,
        "canary_overlap": canary_overlap,
        "prod_overlap": prod_overlap,
        "prod_high_risk_percent": prod_high_risk,
        "checks": checks,
        "pass": all(checks.values()),
    }
