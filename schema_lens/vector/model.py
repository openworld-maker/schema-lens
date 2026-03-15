"""Data models for vector and hybrid simulation runtime configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VectorScenario:
    name: str
    mode: str
    lexical: dict[str, Any] = field(default_factory=dict)
    knn: dict[str, Any] = field(default_factory=dict)
    blend: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VectorRuntimeConfig:
    enabled: bool
    field: str
    dimension: int | None
    similarity: str | None
    query_vector_policy: str
    embedding_source: dict[str, Any] = field(default_factory=dict)
    scenarios: list[VectorScenario] = field(default_factory=list)
    evaluation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scenarios"] = [scenario.to_dict() for scenario in self.scenarios]
        return payload
