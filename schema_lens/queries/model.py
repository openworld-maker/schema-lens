"""Query model definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class QueryCase:
    id: int
    line_no: int
    raw_line: str
    params: dict[str, Any]
    normalized_q: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
