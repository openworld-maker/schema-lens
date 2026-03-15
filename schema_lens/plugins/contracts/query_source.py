"""Query source plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class QuerySourcePlugin(BasePlugin):
    """Provide query inputs to a run."""

    def load_queries(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return []
