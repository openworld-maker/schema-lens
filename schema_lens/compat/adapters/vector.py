"""Vector compatibility adapter."""

from __future__ import annotations

from typing import Any


def vector_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("vector_supported", caps.get("vector_query_supported", False)))


def hybrid_mode(caps: dict[str, Any]) -> str:
    if not vector_supported(caps):
        return "disabled"
    if bool(caps.get("vector_native_hybrid_supported", False)):
        return "native"
    return "client_side"


def vector_runtime_message(caps: dict[str, Any]) -> str:
    mode = hybrid_mode(caps)
    if mode == "disabled":
        return "Vector support unavailable; vector scenarios skipped."
    if mode == "client_side":
        return "Native hybrid vector support unavailable; using client-side hybrid simulation."
    return "Vector and native hybrid support available."
