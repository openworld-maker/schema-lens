"""Configset operation compatibility adapter."""

from __future__ import annotations

from typing import Any


def configset_upload_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("configset_upload_supported", False))
