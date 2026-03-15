"""Sample gate evaluator plugin for schema-lens."""

from __future__ import annotations

from schema_lens.plugins.base import PluginContext, PluginMetadata
from schema_lens.plugins.contracts.gate import GateEvaluatorPlugin


class SampleGatePlugin(GateEvaluatorPlugin):
    metadata = PluginMetadata(
        name="sample_gate",
        version="0.1.0",
        plugin_type="gate",
        capabilities=["quality_gate_hint"],
        schema_lens_version=">=0.1.0,<1.0.0",
    )

    def execute(self, context: PluginContext, payload: dict[str, object]) -> dict[str, object]:
        compare_data = payload.get("compare_data", {})
        summary = compare_data.get("summary", {}) if isinstance(compare_data, dict) else {}
        risk = summary.get("high_risk_percent", 0)
        return {
            "gate": "sample_gate",
            "high_risk_percent": risk,
            "recommended_action": "review" if float(risk or 0) > 20 else "pass",
        }


PLUGIN = SampleGatePlugin
