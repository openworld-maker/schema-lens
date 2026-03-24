"""LTR capability adapter."""

from __future__ import annotations

from typing import Any


def ltr_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("ltr_possible", caps.get("ltr_available", False)))


def feature_logging_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("feature_logging_possible", False))
