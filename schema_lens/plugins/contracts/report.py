"""Report renderer and widget plugin contracts."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class ReportRendererPlugin(BasePlugin):
    """Render additional report outputs."""

    def render_json_section(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        return {}

    def render_html_section(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> str:
        return ""


class ReportWidgetPlugin(BasePlugin):
    """Inject additional report widgets."""

    def render_json_section(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        return self.widget(run_context)

    def render_html_section(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> str:
        widget = self.widget(run_context)
        return str(widget)

    def widget(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}


class ReportPlugin(ReportRendererPlugin):
    """Alias for report renderer plugin contract."""
