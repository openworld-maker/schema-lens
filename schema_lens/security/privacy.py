"""Security profile-driven artifact privacy helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactPrivacyMode:
    profile: str
    summary_only: bool
    persist_sensitive_artifacts: bool


SUMMARY_ONLY_ALLOWED = {
    "run_manifest.json",
    "report.json",
    "report.html",
    "privacy.json",
    "audit.json",
    "governance.json",
}


def mode_from_profile(profile: str) -> ArtifactPrivacyMode:
    key = profile.strip().lower()
    if key == "summary-only":
        return ArtifactPrivacyMode(profile=key, summary_only=True, persist_sensitive_artifacts=False)
    if key == "no-sensitive-artifacts":
        return ArtifactPrivacyMode(profile=key, summary_only=False, persist_sensitive_artifacts=False)
    return ArtifactPrivacyMode(profile=key, summary_only=False, persist_sensitive_artifacts=True)


def artifact_allowed(profile: str, artifact_name: str) -> bool:
    mode = mode_from_profile(profile)
    if not mode.summary_only:
        return True
    return artifact_name in SUMMARY_ONLY_ALLOWED
