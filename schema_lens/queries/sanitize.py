"""Query sanitization helpers for log-derived requests."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


def _sanitize_value(value: Any, rules: list[dict[str, Any]]) -> Any:
    if isinstance(value, list):
        return [_sanitize_value(v, rules) for v in value]
    if not isinstance(value, str):
        return value

    out = value
    for rule in rules:
        rule_type = rule.get("type")
        if rule_type == "mask_email":
            out = EMAIL_RE.sub("<redacted_email>", out)
        elif rule_type == "mask_uuid":
            out = UUID_RE.sub("<redacted_uuid>", out)
    return out


def sanitize_params(
    params: dict[str, Any],
    *,
    enabled: bool = True,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not enabled:
        return dict(params)

    effective_rules = list(rules or [])
    if not effective_rules:
        effective_rules = [
            {"type": "mask_email"},
            {"type": "mask_uuid"},
            {"type": "drop_param", "name": "token"},
            {"type": "drop_param", "name": "auth"},
        ]

    drop_names = {
        str(rule.get("name", "")).lower()
        for rule in effective_rules
        if rule.get("type") == "drop_param"
    }

    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if key.lower() in drop_names:
            continue
        cleaned[key] = _sanitize_value(value, effective_rules)
    return cleaned

