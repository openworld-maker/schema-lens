"""Gate evaluator plugin contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schema_lens.plugins.base import BasePlugin


@dataclass
class GateResult:
    passed: bool
    policy: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    reason: str | None = None


class GateEvaluatorPlugin(BasePlugin):
    """Evaluate policy gates."""

    def evaluate(self, policy: dict[str, Any], artifacts: dict[str, Any]) -> GateResult:
        return GateResult(passed=True)


class GatePlugin(GateEvaluatorPlugin):
    """Alias for GateEvaluatorPlugin."""
