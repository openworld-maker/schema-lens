"""Security execution profile settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityProfile:
    name: str
    redact_artifacts: bool
    persist_sensitive_artifacts: bool


_PROFILES = {
    "local-dev": SecurityProfile(
        name="local-dev",
        redact_artifacts=False,
        persist_sensitive_artifacts=True,
    ),
    "enterprise-safe": SecurityProfile(
        name="enterprise-safe",
        redact_artifacts=True,
        persist_sensitive_artifacts=True,
    ),
    "no-persist-sensitive": SecurityProfile(
        name="no-persist-sensitive",
        redact_artifacts=True,
        persist_sensitive_artifacts=False,
    ),
    "redacted-artifacts-only": SecurityProfile(
        name="redacted-artifacts-only",
        redact_artifacts=True,
        persist_sensitive_artifacts=False,
    ),
}


def resolve_profile(name: str | None) -> SecurityProfile:
    key = (name or "local-dev").strip().lower()
    return _PROFILES.get(key, _PROFILES["local-dev"])
