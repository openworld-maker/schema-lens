"""Recommendation models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Recommendation:
    recommendation_code: str
    rationale: str
    safety_level: str
    implementation_steps: list[str] = field(default_factory=list)
    rollback_hint: str | None = None
    confidence: str = "MEDIUM"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
