"""Collections/alias capability adapter."""

from __future__ import annotations

from typing import Any


def collections_api_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("collections_api_supported", caps.get("collections_api", False)))


def alias_ops_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("alias_ops_supported", caps.get("aliases", False)))
