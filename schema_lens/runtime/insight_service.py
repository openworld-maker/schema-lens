from __future__ import annotations

from typing import Any

from schema_lens.ltr.capture import capture_ltr_impact
from schema_lens.recommend.engine import build_recommendations
from schema_lens.rootcause.engine import analyze_root_causes


def run_root_cause(*, compare_data: dict[str, Any], changes: list[Any], baseline_request_defaults: dict[str, Any]) -> dict[str, Any]:
    return analyze_root_causes(
        compare_data=compare_data,
        changes=changes,
        baseline_request_defaults=baseline_request_defaults,
    )


def run_recommendations(*, root_causes: dict[str, Any]) -> dict[str, Any]:
    return build_recommendations(root_causes)


def run_ltr_impact(*, replay_data: dict[str, Any]) -> dict[str, Any]:
    return capture_ltr_impact(replay_data)
