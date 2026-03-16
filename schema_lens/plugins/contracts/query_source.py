"""Query source plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class QuerySourcePlugin(BasePlugin):
    """Provide query inputs to a run."""

    def validate_source(self, config: dict[str, Any]) -> None:
        return None

    def load_queries(self, config: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        return []
