"""Vector compatibility adapter."""

from __future__ import annotations

from typing import Any


def vector_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("vector_query_supported", False))
