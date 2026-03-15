"""Root cause data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RootCauseFinding:
    cause_code: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    affected_query_classes: list[str] = field(default_factory=list)
    linked_artifacts: dict[str, Any] = field(default_factory=dict)
    query_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
