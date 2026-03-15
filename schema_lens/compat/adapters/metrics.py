"""Metrics compatibility adapter."""

from __future__ import annotations

from typing import Any


def metrics_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("metrics_json_supported", False))
