"""Segment-specific policy evaluation."""

from __future__ import annotations

from typing import Any


def evaluate_segment_policies(
    *,
    segment_report: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    rules = policy.get("rules", []) if isinstance(policy, dict) else []
    by_segment = segment_report.get("by_segment", {}) if isinstance(segment_report, dict) else {}

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        key = str(rule.get("segment_key", ""))
        value = str(rule.get("segment_value", ""))
        metric = str(rule.get("metric", "high_risk_percent"))
        op = str(rule.get("op", ">"))
        threshold = float(rule.get("value", 0.0))
        severity = str(rule.get("severity", "fail"))

        bucket = by_segment.get(f"{key}:{value}")
        if not isinstance(bucket, dict):
            continue
        actual = float(bucket.get(metric, 0.0) or 0.0)
        matched = False
        if op == ">":
            matched = actual > threshold
        elif op == ">=":
            matched = actual >= threshold
        elif op == "<":
            matched = actual < threshold
        elif op == "<=":
            matched = actual <= threshold
        elif op in {"==", "="}:
            matched = actual == threshold

        if matched:
            payload = {**rule, "actual": actual}
            if severity == "warn":
                warnings.append(payload)
            else:
                failures.append(payload)

    return {
        "enabled": bool(rules),
        "pass": len(failures) == 0,
        "failed_rules": failures,
        "warned_rules": warnings,
    }
