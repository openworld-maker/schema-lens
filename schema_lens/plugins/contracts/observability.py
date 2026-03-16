"""Observability exporter plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class ObservabilityExporterPlugin(BasePlugin):
    """Export run telemetry."""

    def on_run_started(self, run_context: dict[str, Any]) -> None:
        return None

    def on_run_completed(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> None:
        return None

    def on_gate_failed(self, run_context: dict[str, Any], gate_result: dict[str, Any]) -> None:
        return None

    def export(self, context: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible alias."""
        return {}
