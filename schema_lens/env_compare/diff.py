"""Environment compare diff helpers."""

from __future__ import annotations

from typing import Any

from schema_lens.compare.diff import compare_replay


def build_environment_compare(
    replay_data: dict[str, Any],
    k: int,
    env1: dict[str, Any],
    env2: dict[str, Any],
    env1_contract: dict[str, Any] | None = None,
    env2_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compare = compare_replay(replay_data, k)
    top1_mismatch = 0
    total = len(compare.get("diffs", []))
    for diff in compare.get("diffs", []):
        base = diff.get("baseline_topk_ids", [])
        shadow = diff.get("shadow_topk_ids", [])
        if base[:1] != shadow[:1]:
            top1_mismatch += 1
    env1_contract = env1_contract if isinstance(env1_contract, dict) else {}
    env2_contract = env2_contract if isinstance(env2_contract, dict) else {}
    env1_caps = env1_contract.get("capabilities", {})
    env2_caps = env2_contract.get("capabilities", {})
    capability_mismatches: list[dict[str, Any]] = []
    if isinstance(env1_caps, dict) and isinstance(env2_caps, dict):
        keys = sorted(set(env1_caps.keys()) | set(env2_caps.keys()))
        for key in keys:
            left = env1_caps.get(key)
            right = env2_caps.get(key)
            if left == right:
                continue
            if isinstance(left, bool) or isinstance(right, bool):
                capability_mismatches.append({"capability": key, "env1": left, "env2": right})

    mismatch_risk = "low"
    if capability_mismatches:
        mismatch_risk = "medium"
    if any(item.get("capability") in {"vector_supported", "structured_explain_supported"} for item in capability_mismatches):
        mismatch_risk = "high"

    compare["environment_compare"] = {
        "enabled": True,
        "env1": env1,
        "env2": env2,
        "compatibility": {
            "env1": env1_contract,
            "env2": env2_contract,
            "capability_mismatches": capability_mismatches,
            "mismatch_risk": mismatch_risk,
        },
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
