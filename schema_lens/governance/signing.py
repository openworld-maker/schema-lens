"""Signed-manifest helpers for governance workflows."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def manifest_hash(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def sign_manifest(manifest: dict[str, Any], secret: str) -> str:
    payload_hash = manifest_hash(manifest)
    digest = hmac.new(secret.encode("utf-8"), payload_hash.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def verify_manifest_signature(manifest: dict[str, Any], secret: str, signature: str) -> bool:
    expected = sign_manifest(manifest, secret)
    return hmac.compare_digest(expected, signature)
