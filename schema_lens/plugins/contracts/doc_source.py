"""Document source plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class DocSourcePlugin(BasePlugin):
    """Provide documents for shadow indexing."""

    def load_docs(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return []
