"""Approval metadata validation helpers."""

from __future__ import annotations

from typing import Any

_REQUIRED_FIELDS = {"requested_by"}
_OPTIONAL_FIELDS = {
    "approved_by",
    "ticket_id",
    "change_request_id",
    "exception_reason",
    "exception_expiry",
}


def validate_approval_metadata(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("approval metadata must be an object")
    missing = [field for field in sorted(_REQUIRED_FIELDS) if not str(data.get(field, "")).strip()]
    if missing:
        raise ValueError(f"approval metadata missing required fields: {', '.join(missing)}")

    allowed = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
    for key in data:
        if key not in allowed:
            raise ValueError(f"approval metadata has unsupported field: {key}")


def normalize_approval_metadata(data: dict[str, Any]) -> dict[str, Any]:
    validate_approval_metadata(data)
    payload: dict[str, Any] = {}
    for key in sorted(_REQUIRED_FIELDS | _OPTIONAL_FIELDS):
        value = data.get(key)
        if value is None:
            continue
        payload[key] = str(value)
    return payload
