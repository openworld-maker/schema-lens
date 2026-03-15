"""Report renderer and widget plugin contracts."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class ReportRendererPlugin(BasePlugin):
    """Render additional report outputs."""

    def render(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}


class ReportWidgetPlugin(BasePlugin):
    """Inject additional report widgets."""

    def widget(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}
