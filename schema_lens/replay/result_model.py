"""Replay result models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryDoc:
    id: str
    score: float | None
    rank: int


@dataclass
class QueryResult:
    query_id: int
    target: str
    docs: list[QueryDoc] = field(default_factory=list)
    raw_response_meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data
