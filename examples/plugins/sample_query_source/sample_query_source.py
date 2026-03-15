"""Sample query source plugin for schema-lens."""

from __future__ import annotations

from schema_lens.plugins.base import PluginContext, PluginMetadata
from schema_lens.plugins.contracts.query_source import QuerySourcePlugin


class SampleQuerySourcePlugin(QuerySourcePlugin):
    metadata = PluginMetadata(
        name="sample_query_source",
        version="0.1.0",
        plugin_type="query_source",
        capabilities=["synthetic_queries"],
        schema_lens_version=">=0.1.0,<1.0.0",
    )

    def execute(self, context: PluginContext, payload: dict[str, object]) -> dict[str, object]:
        return {
            "note": "sample query source plugin executed",
            "run_id": context.run_id,
            "capability": "synthetic_queries",
        }


PLUGIN = SampleQuerySourcePlugin
