"""Golden query model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GoldenQuery:
    name: str
    params: dict[str, Any]
    expected_ids: list[str] = field(default_factory=list)
    must_contain_topk: int = 10

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

