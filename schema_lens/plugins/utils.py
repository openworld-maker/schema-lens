"""Plugin payload helpers."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def normalize_plugin_payload(value: Any) -> Any:
    """Recursively convert dataclasses to serializable dicts/lists."""
    if is_dataclass(value):
        return normalize_plugin_payload(asdict(value))
    if isinstance(value, dict):
        return {key: normalize_plugin_payload(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_plugin_payload(item) for item in value]
    return value
