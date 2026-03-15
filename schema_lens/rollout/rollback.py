"""Rollback plan generation."""

from __future__ import annotations

from typing import Any


def build_rollback_plan(*, alias: str, previous_collection: str) -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "alias": alias,
        "restore_collection": previous_collection,
        "command": {
            "action": "CREATEALIAS",
            "name": alias,
            "collections": previous_collection,
        },
        "steps": [
            "verify_alias_target",
            "apply_alias_restore",
            "run_post_cutover_verify",
        ],
    }
