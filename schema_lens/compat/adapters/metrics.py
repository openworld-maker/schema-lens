"""Metrics compatibility adapter."""

from __future__ import annotations

from typing import Any


def metrics_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("metrics_json_supported", False) or caps.get("metrics_mbeans_supported", False))


def preferred_metrics_source(caps: dict[str, Any]) -> str:
    if bool(caps.get("metrics_json_supported", False)):
        return "metrics"
    if bool(caps.get("metrics_mbeans_supported", False)):
        return "mbeans"
    return "unavailable"


def normalize_metrics_payload(payload: dict[str, Any], source: str) -> dict[str, Any]:
    normalized = payload if isinstance(payload, dict) else {}
    return {
        "source": source,
        "raw": normalized,
        "available": bool(normalized),
    }
