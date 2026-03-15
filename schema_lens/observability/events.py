"""Event schema helpers for observability hooks."""

from __future__ import annotations

from typing import Any

_ALLOWED_EVENT_TYPES = {
    "run_started",
    "run_completed",
    "gate_failed",
    "drift_detected",
}


def build_event(
    *,
    event_type: str,
    timestamp: str,
    run_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": timestamp,
        "run_id": run_id,
        "payload": payload or {},
    }


def validate_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        raise ValueError("event must be an object")
    event_type = event.get("event_type")
    if event_type not in _ALLOWED_EVENT_TYPES:
        raise ValueError(f"unsupported event_type: {event_type}")
    if not isinstance(event.get("timestamp"), str) or not event["timestamp"]:
        raise ValueError("event.timestamp must be non-empty string")
    if not isinstance(event.get("run_id"), str) or not event["run_id"]:
        raise ValueError("event.run_id must be non-empty string")
    payload = event.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("event.payload must be an object")
