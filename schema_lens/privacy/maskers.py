"""PII masking primitives."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_NUMERIC_ID_RE = re.compile(r"\b\d{6,}\b")


def _hash(value: str, salt: str) -> str:
    digest = hashlib.sha256((salt + value).encode("utf-8")).hexdigest()
    return digest[:16]


def mask_text(text: str, *, salt: str, email: bool, uuid: bool, numeric_id_hash: bool) -> str:
    out = text
    if email:
        out = _EMAIL_RE.sub("<email_masked>", out)
    if uuid:
        out = _UUID_RE.sub("<uuid_masked>", out)
    if numeric_id_hash:
        out = _NUMERIC_ID_RE.sub(lambda m: f"<id_{_hash(m.group(0), salt)}>", out)
    return out


def mask_payload(
    payload: Any,
    *,
    salt: str,
    email: bool,
    uuid: bool,
    numeric_id_hash: bool,
    allowlist: list[str] | None = None,
    denylist: list[str] | None = None,
) -> Any:
    allow = set(allowlist or [])
    deny = set(denylist or [])

    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if allow and key not in allow:
                continue
            if key in deny:
                continue
            out[key] = mask_payload(
                value,
                salt=salt,
                email=email,
                uuid=uuid,
                numeric_id_hash=numeric_id_hash,
                allowlist=None,
                denylist=denylist,
            )
        return out
    if isinstance(payload, list):
        return [
            mask_payload(
                item,
                salt=salt,
                email=email,
                uuid=uuid,
                numeric_id_hash=numeric_id_hash,
                allowlist=None,
                denylist=denylist,
            )
            for item in payload
        ]
    if isinstance(payload, str):
        return mask_text(
            payload,
            salt=salt,
            email=email,
            uuid=uuid,
            numeric_id_hash=numeric_id_hash,
        )
    return payload
