"""Sample report widget plugin for schema-lens."""

from __future__ import annotations

from schema_lens.plugins.base import PluginContext, PluginMetadata
from schema_lens.plugins.contracts.report import ReportWidgetPlugin


class SampleReportWidgetPlugin(ReportWidgetPlugin):
    metadata = PluginMetadata(
        name="sample_report_widget",
        version="0.1.0",
        plugin_type="report_widget",
        capabilities=["widget"],
        schema_lens_version=">=0.1.0,<1.0.0",
    )

    def execute(self, context: PluginContext, payload: dict[str, object]) -> dict[str, object]:
        return {
            "widget": {
                "title": "Plugin Widget",
                "body": f"Run {context.run_id} completed with plugin widget output.",
            }
        }


PLUGIN = SampleReportWidgetPlugin
