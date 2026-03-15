from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schema_lens.errors import StageError
from schema_lens.governance import (
    manifest_hash as governance_manifest_hash,
    merge_policy_bundles,
    normalize_approval_metadata,
    sign_manifest,
    validate_exception_records,
    validate_promotion_state,
)


@dataclass
class GovernanceRuntime:
    data: dict[str, Any]
    sign_secret: str | None = None


def initialize_governance(
    *,
    changeset_raw: dict[str, Any],
    changeset_path: Path,
) -> GovernanceRuntime:
    gov_cfg = changeset_raw.get("governance", {})
    if not isinstance(gov_cfg, dict):
        gov_cfg = {}
    enabled = bool(gov_cfg.get("enabled", False))
    data: dict[str, Any] = {"enabled": enabled}
    sign_secret: str | None = None

    if enabled:
        approval_raw = gov_cfg.get("approval", {})
        approval = normalize_approval_metadata(approval_raw) if isinstance(approval_raw, dict) else {}
        if not approval:
            raise StageError("governance.enabled=true requires governance.approval metadata")

        promotion_state = validate_promotion_state(str(gov_cfg.get("promotion_state", "dev")))

        exceptions_raw = gov_cfg.get("exceptions", [])
        exceptions = validate_exception_records(exceptions_raw) if isinstance(exceptions_raw, list) else []

        bundle_paths_raw = gov_cfg.get("policy_bundles", [])
        bundle_paths: list[Path] = []
        if isinstance(bundle_paths_raw, list):
            for item in bundle_paths_raw:
                if not isinstance(item, str):
                    continue
                path = Path(item)
                if not path.is_absolute():
                    path = (changeset_path.parent / path).resolve()
                bundle_paths.append(path)

        bundles_merged = merge_policy_bundles(bundle_paths) if bundle_paths else {"fail": [], "warn": []}

        signing_cfg = gov_cfg.get("signing", {})
        if not isinstance(signing_cfg, dict):
            signing_cfg = {}
        signing_enabled = bool(signing_cfg.get("enabled", False))
        secret_env = signing_cfg.get("secret_env")
        secret_value = signing_cfg.get("secret")
        if signing_enabled:
            if isinstance(secret_value, str) and secret_value:
                sign_secret = secret_value
            elif isinstance(secret_env, str) and secret_env:
                sign_secret = os.getenv(secret_env)
            if not sign_secret:
                raise StageError("governance.signing.enabled=true requires signing.secret or signing.secret_env")

        data = {
            "enabled": True,
            "approval": approval,
            "promotion_state": promotion_state,
            "exceptions": exceptions,
            "policy_bundle_paths": [str(path) for path in bundle_paths],
            "policy_bundle_merged": bundles_merged,
            "signing": {
                "enabled": signing_enabled,
                "algorithm": "hmac-sha256" if signing_enabled else None,
            },
        }

    return GovernanceRuntime(data=data, sign_secret=sign_secret)


def finalize_governance_manifest(
    *,
    manifest_payload: dict[str, Any],
    governance_settings: dict[str, Any],
    sign_secret: str | None,
) -> dict[str, Any]:
    if not bool(governance_settings.get("enabled")):
        return governance_settings

    finalized = dict(governance_settings)
    finalized["manifest_hash"] = governance_manifest_hash(manifest_payload)
    if sign_secret:
        finalized["signature"] = sign_manifest(manifest_payload, sign_secret)
    return finalized
