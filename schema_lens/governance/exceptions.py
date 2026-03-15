"""Governance exception record handling."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_iso8601(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def validate_exception_record(record: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("exception record must be an object")
    required = ["id", "rationale", "expiry"]
    missing = [key for key in required if not str(record.get(key, "")).strip()]
    if missing:
        raise ValueError(f"exception record missing required fields: {', '.join(missing)}")

    expiry = _parse_iso8601(str(record["expiry"]))
    current = now or datetime.now(timezone.utc)
    return {
        "id": str(record["id"]),
        "rationale": str(record["rationale"]),
        "approved_by": str(record.get("approved_by", "")),
        "expiry": expiry.isoformat(),
        "expired": expiry < current,
    }


def validate_exception_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError("exceptions must be a list")
    return [validate_exception_record(item) for item in records]
