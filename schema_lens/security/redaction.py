"""Payload redaction helpers for artifacts and logs."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit
from typing import Any


REDACTED = "***REDACTED***"
DEFAULT_SENSITIVE_KEYS = {
    "authorization",
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "bearer",
    "private_key",
    "key_file",
    "cert_file",
    "client_secret",
}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            redacted[key] = REDACTED
        else:
            redacted[key] = value
    return redacted


def redact_dict(data: Any, *, sensitive_keys: set[str] | None = None, extra_sensitive_keys: list[str] | None = None) -> Any:
    sensitive = set(DEFAULT_SENSITIVE_KEYS)
    if sensitive_keys:
        sensitive.update(item.lower() for item in sensitive_keys)
    if extra_sensitive_keys:
        sensitive.update(item.lower() for item in extra_sensitive_keys)

    if isinstance(data, dict):
        output: dict[str, Any] = {}
        for key, value in data.items():
            lowered = key.lower()
            if lowered in sensitive:
                output[key] = REDACTED
                continue
            if lowered == "headers" and isinstance(value, dict):
                output[key] = redact_headers({str(k): str(v) for k, v in value.items()})
                continue
            output[key] = redact_dict(
                value,
                sensitive_keys=sensitive,
                extra_sensitive_keys=extra_sensitive_keys,
            )
        return output
    if isinstance(data, list):
        return [
            redact_dict(
                item,
                sensitive_keys=sensitive,
                extra_sensitive_keys=extra_sensitive_keys,
            )
            for item in data
        ]
    return data


def redact_url(url: str) -> str:
    """Redact credential-bearing URLs."""
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    if "@" in parts.netloc:
        host = parts.netloc.split("@", 1)[1]
        redacted_netloc = f"{REDACTED}@{host}"
        return urlunsplit((parts.scheme, redacted_netloc, parts.path, parts.query, parts.fragment))
    return url


def redact_text(text: str) -> str:
    """Best-effort redaction for common secret patterns in plain text."""
    patterns = [
        re.compile(r"(?i)(authorization\s*:\s*)(.+)"),
        re.compile(r"(?i)(bearer\s+)([^\s]+)"),
        re.compile(r"(?i)(password\s*[=:]\s*)([^\s,;]+)"),
        re.compile(r"(?i)(token\s*[=:]\s*)([^\s,;]+)"),
        re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;]+)"),
    ]
    out = text
    for pattern in patterns:
        out = pattern.sub(rf"\\1{REDACTED}", out)
    return out


def redact_payload(data: Any, *, extra_sensitive_keys: list[str] | None = None) -> Any:
    return redact_dict(data, extra_sensitive_keys=extra_sensitive_keys)


def redact_auth_config(auth: dict[str, Any]) -> dict[str, Any]:
    return redact_dict(auth)
