"""Explain compatibility adapter."""

from __future__ import annotations

from typing import Any


def structured_explain_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("structured_explain_supported", False))
