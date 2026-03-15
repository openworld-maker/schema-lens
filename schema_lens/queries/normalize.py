"""Query normalization helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_q(params: dict[str, Any] | None) -> str:
    if not isinstance(params, dict):
        return ""
    q = params.get("q", "")
    if isinstance(q, list):
        return str(q[0]) if q else ""
    return str(q)


def query_fingerprint(payload: dict[str, Any] | None) -> str:
    normalized = payload if isinstance(payload, dict) else {}
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
