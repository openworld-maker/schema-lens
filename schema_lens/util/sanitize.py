"""Sanitization helpers."""

from __future__ import annotations

import re

_SAFE_RE = re.compile(r"[^a-zA-Z0-9_\-]+")


def safe_name(value: str) -> str:
    return _SAFE_RE.sub("_", value).strip("_")
