"""Lightweight OTel-style span recording with no-op fallback."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from time import perf_counter
from typing import Any


@dataclass
class SpanRecord:
    name: str
    started_at: str
    ended_at: str
    duration_seconds: float
    attributes: dict[str, Any]


class OTelRecorder:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._active: dict[str, tuple[float, str, dict[str, Any]]] = {}
        self.spans: list[SpanRecord] = []

    def start_span(self, span_id: str, *, name: str, started_at: str, attributes: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._active[span_id] = (perf_counter(), started_at, dict(attributes))

    def end_span(self, span_id: str, *, ended_at: str) -> None:
        if not self.enabled:
            return
        active = self._active.pop(span_id, None)
        if active is None:
            return
        started_perf, started_at, attrs = active
        self.spans.append(
            SpanRecord(
                name=span_id,
                started_at=started_at,
                ended_at=ended_at,
                duration_seconds=round(perf_counter() - started_perf, 6),
                attributes=attrs,
            )
        )

    def export(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "spans": [asdict(span) for span in self.spans],
        }
