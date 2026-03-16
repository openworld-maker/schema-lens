"""Sample report plugin for SolrGuard."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import PluginContext, PluginMetadata
from schema_lens.plugins.contracts.report import ReportRendererPlugin


class SampleReportPlugin(ReportRendererPlugin):
    metadata = PluginMetadata(
        name="sample_report",
        version="0.1.0",
        plugin_type="report",
        description="Adds Plugin Summary report section grouped by tenant or query_class.",
        compatible_schema_lens_version=">=0.1.0",
        capabilities=["report:json_section", "report:html_section"],
    )

    def _group_counts(self, group_by: str, artifacts: dict[str, Any]) -> dict[str, int]:
        replay_data = artifacts.get("replay_data", {})
        pairs = replay_data.get("pairs", []) if isinstance(replay_data, dict) else []
        counts: dict[str, int] = {}
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            query = pair.get("query", {})
            if not isinstance(query, dict):
                continue
            segment = query.get("segment", {})
            if isinstance(segment, dict) and group_by in segment:
                key = str(segment[group_by])
            else:
                params = query.get("params", {})
                if isinstance(params, dict) and group_by in params:
                    key = str(params[group_by])
                else:
                    key = "unknown"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def render_json_section(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        config = run_context.get("plugin_config", {})
        if not isinstance(config, dict):
            config = {}
        group_by = str(config.get("group_by", "tenant"))
        return {
            "title": "Plugin Summary",
            "group_by": group_by,
            "counts": self._group_counts(group_by, artifacts),
        }

    def render_html_section(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> str:
        section = self.render_json_section(run_context, artifacts)
        counts = section.get("counts", {})
        rows = "".join(
            f"<li><strong>{key}</strong>: {value}</li>"
            for key, value in sorted(counts.items(), key=lambda item: item[0])
        )
        return f"<section><h3>Plugin Summary</h3><ul>{rows}</ul></section>"

    def execute(self, context: PluginContext, payload: dict[str, object]) -> dict[str, object]:
        config = context.get_plugin_config(self.metadata.name)
        run_context = {"run_id": context.run_id, "plugin_config": config}
        artifacts = {
            "compare_data": payload.get("compare_data", {}),
            "replay_data": payload.get("replay_data", {}),
            "manifest": payload.get("manifest", {}),
        }
        return {
            "json_section": self.render_json_section(run_context, artifacts),
            "html_section": self.render_html_section(run_context, artifacts),
        }


PLUGIN = SampleReportPlugin

