"""Replay executor plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class ReplayExecutorPlugin(BasePlugin):
    """Provide replay execution for custom transport/execution models."""

    def replay(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}
