"""Privacy profile resolution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrivacyProfile:
    name: str
    mask_email: bool
    mask_uuid: bool
    numeric_id_hash: bool
    export_safe: bool
    raw_doc_suppression: bool
    hashed_doc_id_only: bool


_PROFILES = {
    "off": PrivacyProfile("off", False, False, False, False, False, False),
    "default": PrivacyProfile("default", True, True, True, False, False, False),
    "export-safe": PrivacyProfile("export-safe", True, True, True, True, True, True),
}


def resolve_privacy_profile(name: str | None) -> PrivacyProfile:
    key = (name or "off").strip().lower()
    return _PROFILES.get(key, _PROFILES["off"])
