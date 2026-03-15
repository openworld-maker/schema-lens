from __future__ import annotations

from typing import Any

from schema_lens.changesets.apply_queryparams import merge_queryparams
from schema_lens.compare.diff import compare_replay
from schema_lens.replay.runner import run_replay


def run_replay_stage(
    *,
    baseline_client,
    baseline_collection: str,
    shadow_client,
    shadow_collection: str,
    query_cases,
    request_defaults: dict[str, Any],
    changes: list[Any],
    replay_cfg: dict[str, Any],
    k: int,
    baseline_url: str,
    shadow_url: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged_defaults = merge_queryparams(request_defaults, changes)
    capture_cfg = replay_cfg.get("capture", {}) if isinstance(replay_cfg, dict) else {}
    if not isinstance(capture_cfg, dict):
        capture_cfg = {}

    replay_data = run_replay(
        baseline_client=baseline_client,
        baseline_collection=baseline_collection,
        shadow_client=shadow_client,
        shadow_collection=shadow_collection,
        queries=query_cases,
        request_defaults=merged_defaults,
        k=k,
        capture_cfg=capture_cfg,
    )
    replay_data["baseline"] = {
        "solr_url": baseline_url,
        "collection": baseline_collection,
    }
    replay_data["shadow"] = {
        "solr_url": shadow_url,
        "collection": shadow_collection,
    }
    return replay_data, capture_cfg


def run_compare_stage(
    *,
    replay_data: dict[str, Any],
    k: int,
    schema_risk_data: dict[str, Any],
    compatibility: dict[str, Any],
    governance: dict[str, Any],
) -> dict[str, Any]:
    compare_data = compare_replay(replay_data, k)
    compare_data["schema_safety_findings"] = schema_risk_data
    compare_data["compatibility"] = compatibility
    compare_data["governance"] = governance
    return compare_data
