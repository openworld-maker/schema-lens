"""Audit helpers for security-sensitive runs."""

from __future__ import annotations

from typing import Any


def build_audit_record(
    *,
    run_id: str,
    timestamp: str,
    profile: str,
    requested_by: str | None,
    team: str | None,
    ticket_id: str | None,
    environment_label: str | None,
    notes: str | None,
    baseline_url: str,
    baseline_collection: str,
    shadow_url: str,
    shadow_collection: str,
    baseline_auth_mode: str,
    shadow_auth_mode: str,
    plugins: list[str] | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "security_profile": profile,
        "requested_by": requested_by,
        "team": team,
        "ticket_id": ticket_id,
        "environment_label": environment_label,
        "notes": notes,
        "plugins": plugins or [],
        "outcome": outcome or "started",
        "targets": {
            "baseline": {
                "solr_url": baseline_url,
                "collection": baseline_collection,
                "auth_mode": baseline_auth_mode,
            },
            "shadow": {
                "solr_url": shadow_url,
                "collection": shadow_collection,
                "auth_mode": shadow_auth_mode,
            },
        },
    }
