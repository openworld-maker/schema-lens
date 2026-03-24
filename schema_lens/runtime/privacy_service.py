from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schema_lens.privacy import build_privacy_report, enforce_retention, resolve_privacy_profile


@dataclass
class PrivacyRuntime:
    config: dict[str, Any]
    persist_sensitive_effective: bool


def initialize_privacy(
    *,
    changeset_raw: dict[str, Any],
    security_persist_sensitive: bool,
    security_profile_name: str = "local-dev",
) -> PrivacyRuntime:
    privacy_cfg = changeset_raw.get("privacy", {})
    if not isinstance(privacy_cfg, dict):
        privacy_cfg = {}

    profile = resolve_privacy_profile(str(privacy_cfg.get("profile", "off")))
    runtime_cfg = {
        "enabled": profile.name != "off",
        "profile": profile.name,
        "security_profile": security_profile_name,
        "mask_email": profile.mask_email,
        "mask_uuid": profile.mask_uuid,
        "numeric_id_hash": profile.numeric_id_hash,
        "export_safe": profile.export_safe,
        "raw_doc_suppression": profile.raw_doc_suppression,
        "hashed_doc_id_only": profile.hashed_doc_id_only,
        "allowlist": privacy_cfg.get("allowlist", []) if isinstance(privacy_cfg.get("allowlist"), list) else [],
        "denylist": privacy_cfg.get("denylist", []) if isinstance(privacy_cfg.get("denylist"), list) else [],
        "salt": str(privacy_cfg.get("hash_salt", "solrguard")),
        "persist_sensitive": not bool(privacy_cfg.get("no_persist_sensitive", False)),
    }
    persist_sensitive_effective = bool(security_persist_sensitive) and bool(runtime_cfg.get("persist_sensitive", True))
    return PrivacyRuntime(config=runtime_cfg, persist_sensitive_effective=persist_sensitive_effective)


def build_and_enforce_privacy_report(
    *,
    out_dir: Path,
    runtime_cfg: dict[str, Any],
    persist_sensitive_effective: bool,
) -> tuple[dict[str, Any], list[str]]:
    summary_only = str(runtime_cfg.get("security_profile", "")).strip().lower() == "summary-only"
    deleted = enforce_retention(
        out_dir.resolve(),
        persist_sensitive=bool(persist_sensitive_effective),
        summary_only=summary_only,
    )
    report = build_privacy_report(
        profile=str(runtime_cfg.get("profile", "off")),
        masked_fields=["email", "uuid", "numeric_id"] if bool(runtime_cfg.get("enabled", False)) else [],
        dropped_fields=(
            ["docs_sample.jsonl", "queries_extracted.jsonl", "replay.json"]
            if bool(runtime_cfg.get("raw_doc_suppression", False))
            else []
        ),
        retention_deleted=deleted,
        export_safe=bool(runtime_cfg.get("export_safe", False)),
    )
    return report, deleted
