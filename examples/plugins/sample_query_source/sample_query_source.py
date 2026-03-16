"""Sample query source plugin for SolrGuard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.plugins.base import PluginMetadata
from schema_lens.plugins.contracts.query_source import QuerySourcePlugin


class SampleQuerySourcePlugin(QuerySourcePlugin):
    metadata = PluginMetadata(
        name="sample_query_source",
        version="0.1.0",
        plugin_type="query_source",
        description="Loads custom JSON query rows with query_text/filters/tenant fields.",
        compatible_schema_lens_version=">=0.1.0",
        capabilities=["query_source:file", "query_source:custom_json"],
    )

    def validate_source(self, config: dict[str, Any]) -> None:
        path = config.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("sample_query_source requires config.path")

    def load_queries(self, config: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        base = Path(context.get("changeset_path", ".")).resolve().parent
        source = Path(str(config["path"]))
        if not source.is_absolute():
            cwd_candidate = (Path.cwd() / source).resolve()
            source = cwd_candidate if cwd_candidate.exists() else (base / source).resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("sample_query_source expects a JSON array")

        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "query_text": str(item.get("query_text", "")),
                    "filters": item.get("filters", []),
                    "tenant": item.get("tenant", "default"),
                    "query_class": item.get("query_class", "unknown"),
                }
            )
        return rows

    def execute(self, context, payload):  # type: ignore[no-untyped-def]
        return {"loaded_by": self.metadata.name, "phase": context.phase}


PLUGIN = SampleQuerySourcePlugin
