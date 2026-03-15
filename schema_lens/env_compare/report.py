"""Environment compare report helpers."""

from __future__ import annotations

from typing import Any


def summarize_environment_compare(compare_data: dict[str, Any]) -> list[str]:
    env = compare_data.get("environment_compare", {})
    summary = env.get("summary", {}) if isinstance(env, dict) else {}
    return [
        f"Top1 mismatch: {float(summary.get('top1_mismatch_percent', 0.0)):.2f}%",
        f"Top10 overlap < 0.7: {float(summary.get('top10_overlap_lt_0_7_percent', 0.0)):.2f}%",
    ]
