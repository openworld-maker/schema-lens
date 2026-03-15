"""Audit helpers for security-sensitive runs."""

from __future__ import annotations

from typing import Any


def build_audit_record(
    *,
    run_id: str,
    timestamp: str,
    profile: str,
    requested_by: str | None,
    approval_reference: str | None,
    baseline_url: str,
    baseline_collection: str,
    shadow_url: str,
    shadow_collection: str,
    baseline_auth_mode: str,
    shadow_auth_mode: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "profile": profile,
        "requested_by": requested_by,
        "approval_reference": approval_reference,
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
