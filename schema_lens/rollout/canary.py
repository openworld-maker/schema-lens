"""Canary rollout planning."""

from __future__ import annotations

from typing import Any


def build_canary_plan(
    *,
    baseline_collection: str,
    canary_collection: str,
    traffic_sample_ratio: float,
    replay_query_count: int,
    policy_bundle_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "baseline_collection": baseline_collection,
        "canary_collection": canary_collection,
        "traffic_sample_ratio": max(0.0, min(1.0, float(traffic_sample_ratio))),
        "replay_query_count": max(0, int(replay_query_count)),
        "policy_bundle_paths": policy_bundle_paths or [],
        "steps": [
            "create_canary_collection",
            "index_shadow_docs",
            "replay_sampled_traffic",
            "evaluate_policy_bundles",
            "produce_cutover_checklist",
        ],
    }
