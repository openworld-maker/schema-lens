"""Rollout orchestration plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class RolloutProviderPlugin(BasePlugin):
    """Provide rollout planning operations."""

    def plan_rollout(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_rollout(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def generate_rollback(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def plan(self, context: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible alias."""
        return {}
