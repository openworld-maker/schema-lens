"""Segment model helpers."""

from __future__ import annotations

from typing import Any


DEFAULT_SEGMENT_KEYS = ["tenant", "region", "locale", "catalog"]


def normalize_segment(segment: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(segment, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in segment.items():
        if not isinstance(key, str) or value is None:
            continue
        out[key] = str(value)
    return out
