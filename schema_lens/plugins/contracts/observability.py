"""Observability exporter plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class ObservabilityExporterPlugin(BasePlugin):
    """Export run telemetry."""

    def export(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}
