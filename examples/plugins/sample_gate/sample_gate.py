"""Sample gate evaluator plugin for SolrGuard."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import PluginContext, PluginMetadata
from schema_lens.plugins.contracts.gate import GateEvaluatorPlugin, GateResult


class SampleGatePlugin(GateEvaluatorPlugin):
    metadata = PluginMetadata(
        name="sample_gate",
        version="0.1.0",
        plugin_type="gate",
        description="Fail if too many queries fall under configured overlap threshold.",
        compatible_schema_lens_version=">=0.1.0",
        capabilities=["gate:overlap_policy"],
    )

    def validate_config(self, config: dict[str, Any]) -> None:
        threshold = float(config.get("overlap_threshold", 0.5))
        pct = float(config.get("failure_pct", 30))
        if not (0 <= threshold <= 1):
            raise ValueError("sample_gate overlap_threshold must be between 0 and 1")
        if not (0 <= pct <= 100):
            raise ValueError("sample_gate failure_pct must be between 0 and 100")

    def evaluate(self, policy: dict[str, Any], artifacts: dict[str, Any]) -> GateResult:
        compare_data = artifacts.get("compare_data", {})
        diffs = compare_data.get("diffs", []) if isinstance(compare_data, dict) else []
        overlap_threshold = float(policy.get("overlap_threshold", 0.5))
        failure_pct = float(policy.get("failure_pct", 30))
        if not isinstance(diffs, list) or not diffs:
            return {
                "passed": True,
                "reason": "no_diffs",
                "overlap_threshold": overlap_threshold,
                "failure_pct": failure_pct,
            }

        low_overlap = 0
        for diff in diffs:
            if not isinstance(diff, dict):
                continue
            overlap = diff.get("jaccard")
            if overlap is None:
                overlap = diff.get("topk_overlap_ratio")
            try:
                overlap_value = float(overlap)
            except (TypeError, ValueError):
                continue
            if overlap_value < overlap_threshold:
                low_overlap += 1

        evaluated = len(diffs)
        observed_pct = (low_overlap / evaluated) * 100 if evaluated else 0.0
        passed = observed_pct <= failure_pct
        return GateResult(
            passed=passed,
            policy={
                "overlap_threshold": overlap_threshold,
                "failure_pct": failure_pct,
            },
            stats={
                "evaluated": evaluated,
                "low_overlap": low_overlap,
                "observed_failure_pct": round(observed_pct, 2),
            },
            reason="low_overlap" if not passed else "within_threshold",
        )

    def execute(self, context: PluginContext, payload: dict[str, object]) -> dict[str, object]:
        compare_data = payload.get("compare_data", {})
        result = self.evaluate({}, {"compare_data": compare_data})
        return {"gate": "sample_gate", "evaluation": result, "phase": context.phase}


PLUGIN = SampleGatePlugin
