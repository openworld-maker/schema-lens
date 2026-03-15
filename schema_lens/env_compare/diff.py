"""Environment compare diff helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.compare.diff import compare_replay


def build_environment_compare(
    replay_data: dict[str, Any],
    k: int,
    env1: dict[str, Any],
    env2: dict[str, Any],
) -> dict[str, Any]:
    compare = compare_replay(replay_data, k)
    top1_mismatch = 0
    total = len(compare.get("diffs", []))
    for diff in compare.get("diffs", []):
        base = diff.get("baseline_topk_ids", [])
        shadow = diff.get("shadow_topk_ids", [])
        if base[:1] != shadow[:1]:
            top1_mismatch += 1
    compare["environment_compare"] = {
        "enabled": True,
        "env1": env1,
        "env2": env2,
        "summary": {
            "top1_mismatch_percent": (top1_mismatch / total * 100.0) if total else 0.0,
            "top10_overlap_lt_0_7_percent": (
                len(
                    [
                        diff_row
                        for diff_row in compare.get("diffs", [])
                        if float(diff_row.get("overlap_ratio", 0.0)) < 0.7
                    ]
                )
                / total
                * 100.0
            )
            if total
            else 0.0,
        },
    }
    return compare
