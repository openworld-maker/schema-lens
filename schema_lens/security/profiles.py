"""Security execution profile settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityProfile:
    name: str
    redact_artifacts: bool
    persist_sensitive_artifacts: bool
    summary_only: bool
    persist_raw_requests: bool
    persist_raw_docs: bool
    persist_debug_payloads: bool


_PROFILES = {
    "local-dev": SecurityProfile(
        name="local-dev",
        redact_artifacts=False,
        persist_sensitive_artifacts=True,
        summary_only=False,
        persist_raw_requests=True,
        persist_raw_docs=True,
        persist_debug_payloads=True,
    ),
    "enterprise-safe": SecurityProfile(
        name="enterprise-safe",
        redact_artifacts=True,
        persist_sensitive_artifacts=True,
        summary_only=False,
        persist_raw_requests=False,
        persist_raw_docs=False,
        persist_debug_payloads=False,
    ),
    "no-sensitive-artifacts": SecurityProfile(
        name="no-sensitive-artifacts",
        redact_artifacts=True,
        persist_sensitive_artifacts=False,
        summary_only=False,
        persist_raw_requests=False,
        persist_raw_docs=False,
        persist_debug_payloads=False,
    ),
    "summary-only": SecurityProfile(
        name="summary-only",
        redact_artifacts=True,
        persist_sensitive_artifacts=False,
        summary_only=True,
        persist_raw_requests=False,
        persist_raw_docs=False,
        persist_debug_payloads=False,
    ),
}


def resolve_profile(name: str | None) -> SecurityProfile:
    key = (name or "local-dev").strip().lower()
    if key not in _PROFILES:
        raise ValueError(f"unknown security profile: {name}")
    return _PROFILES[key]
