"""Gate evaluator plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class GateEvaluatorPlugin(BasePlugin):
    """Evaluate policy gates."""

    def evaluate(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}
