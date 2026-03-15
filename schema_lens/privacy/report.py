"""Privacy report generation."""

from __future__ import annotations

from typing import Any


def build_privacy_report(
    *,
    profile: str,
    masked_fields: list[str],
    dropped_fields: list[str],
    retention_deleted: list[str],
    export_safe: bool,
) -> dict[str, Any]:
    return {
        "enabled": profile != "off",
        "profile": profile,
        "masked_fields": masked_fields,
        "dropped_fields": dropped_fields,
        "retention_deleted": retention_deleted,
        "export_safe": export_safe,
    }
