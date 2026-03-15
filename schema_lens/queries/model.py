"""Query model definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryCase:
    id: int
    line_no: int
    raw_line: str
    params: dict[str, Any] | None
    normalized_q: str
    fingerprint: str
    name: str | None = None
    json_request: dict[str, Any] | None = None
    query_vector: list[float] | None = None
    request_mode: str = "params"
    skip_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
