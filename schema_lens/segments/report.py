"""Segment report assembly."""

from __future__ import annotations

from typing import Any

from schema_lens.segments.grouping import aggregate_by_segment
from schema_lens.segments.policy import evaluate_segment_policies


def build_segment_report(
    *,
    compare_data: dict[str, Any],
    policy: dict[str, Any] | None = None,
    segment_keys: list[str] | None = None,
) -> dict[str, Any]:
    diffs = compare_data.get("diffs", []) if isinstance(compare_data, dict) else []
    report = aggregate_by_segment(diffs if isinstance(diffs, list) else [], segment_keys=segment_keys)
    policy_result = evaluate_segment_policies(segment_report=report, policy=policy or {})
    report["policy"] = policy_result
    return report
