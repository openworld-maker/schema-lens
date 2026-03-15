"""Payload redaction helpers for artifacts and logs."""

from __future__ import annotations

from typing import Any


DEFAULT_SENSITIVE_KEYS = {
    "authorization",
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "client_secret",
    "private_key",
}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


def redact_payload(data: Any, *, extra_sensitive_keys: list[str] | None = None) -> Any:
    sensitive = set(DEFAULT_SENSITIVE_KEYS)
    if extra_sensitive_keys:
        sensitive.update(item.lower() for item in extra_sensitive_keys)

    if isinstance(data, dict):
        output: dict[str, Any] = {}
        for key, value in data.items():
            lowered = key.lower()
            if lowered in sensitive:
                output[key] = "<redacted>"
                continue
            if lowered == "headers" and isinstance(value, dict):
                output[key] = redact_headers({str(k): str(v) for k, v in value.items()})
                continue
            output[key] = redact_payload(value, extra_sensitive_keys=extra_sensitive_keys)
        return output
    if isinstance(data, list):
        return [redact_payload(item, extra_sensitive_keys=extra_sensitive_keys) for item in data]
    return data


def redact_auth_config(auth: dict[str, Any]) -> dict[str, Any]:
    return redact_payload(auth)
