from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from schema_lens.errors import StageError
from schema_lens.http.client import SolrHttpClient
from schema_lens.security import (
    AuthResolutionError,
    build_audit_record,
    redact_auth_config,
    resolve_auth_material,
    resolve_profile,
)


@dataclass
class SecurityRuntime:
    profile_name: str
    redact_artifacts: bool
    persist_sensitive_artifacts: bool
    extra_sensitive_keys: list[str]
    baseline_client: SolrHttpClient
    shadow_client: SolrHttpClient
    manifest_security: dict[str, Any]


def initialize_security(
    *,
    changeset_raw: dict[str, Any],
    changeset_path: Path,
    baseline_cfg: dict[str, Any],
    shadow_cfg: dict[str, Any],
    active_auth_plugins: list[Any],
    run_id: str,
    started: str,
    baseline_url: str,
    baseline_collection: str,
    shadow_url: str,
    verbose: bool,
    write_audit: Callable[[dict[str, Any], bool, list[str] | None], None],
) -> SecurityRuntime:
    security_cfg = changeset_raw.get("security", {})
    if not isinstance(security_cfg, dict):
        security_cfg = {}

    security_config_path = security_cfg.get("config")
    if isinstance(security_config_path, str) and security_config_path:
        cfg_path = Path(security_config_path)
        if not cfg_path.is_absolute():
            cfg_path = (changeset_path.parent / cfg_path).resolve()
        loaded_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(loaded_cfg, dict):
            raise StageError("security.config YAML must be an object")
        security_cfg = {**loaded_cfg, **security_cfg}

    profile = resolve_profile(str(security_cfg.get("profile", "local-dev")))
    extra_sensitive_keys_raw = security_cfg.get("extra_sensitive_keys", [])
    extra_sensitive_keys = [str(item) for item in extra_sensitive_keys_raw if isinstance(item, str)]

    baseline_auth_cfg = (
        security_cfg.get("baseline_auth")
        if isinstance(security_cfg.get("baseline_auth"), dict)
        else (baseline_cfg.get("auth") if isinstance(baseline_cfg.get("auth"), dict) else {})
    )
    shadow_auth_cfg = (
        security_cfg.get("shadow_auth")
        if isinstance(security_cfg.get("shadow_auth"), dict)
        else (
            shadow_cfg.get("auth")
            if isinstance(shadow_cfg.get("auth"), dict)
            else baseline_auth_cfg
        )
    )

    plugin_ctx = {
        "run_id": run_id,
        "changeset_path": str(changeset_path.resolve()),
        "baseline_url": baseline_url,
        "shadow_url": shadow_url,
    }
    try:
        baseline_auth = resolve_auth_material(
            baseline_auth_cfg,
            base_dir=changeset_path.parent.resolve(),
            auth_plugins=active_auth_plugins,
            plugin_context=plugin_ctx,
        )
        shadow_auth = resolve_auth_material(
            shadow_auth_cfg,
            base_dir=changeset_path.parent.resolve(),
            auth_plugins=active_auth_plugins,
            plugin_context=plugin_ctx,
        )
    except AuthResolutionError as exc:
        raise StageError(f"security auth resolution failed: {exc}") from exc

    baseline_client = SolrHttpClient(
        baseline_url,
        headers=baseline_auth.headers,
        cert=baseline_auth.cert,
        verify=baseline_auth.verify,
        verbose=verbose,
    )
    shadow_client = SolrHttpClient(
        shadow_url,
        headers=shadow_auth.headers,
        cert=shadow_auth.cert,
        verify=shadow_auth.verify,
        verbose=verbose,
    )

    audit_cfg = security_cfg.get("audit", {})
    if not isinstance(audit_cfg, dict):
        audit_cfg = {}
    requested_by = str(audit_cfg.get("requested_by")) if audit_cfg.get("requested_by") is not None else None
    approval_reference = (
        str(audit_cfg.get("approval_reference")) if audit_cfg.get("approval_reference") is not None else None
    )
    audit_record = build_audit_record(
        run_id=run_id,
        timestamp=started,
        profile=profile.name,
        requested_by=requested_by,
        approval_reference=approval_reference,
        baseline_url=baseline_url,
        baseline_collection=baseline_collection,
        shadow_url=shadow_url,
        shadow_collection=str(shadow_cfg.get("name_prefix", "shadow")),
        baseline_auth_mode=baseline_auth.mode,
        shadow_auth_mode=shadow_auth.mode,
    )

    write_audit(audit_record, profile.redact_artifacts, extra_sensitive_keys)

    manifest_security = {
        "profile": profile.name,
        "redact_artifacts": profile.redact_artifacts,
        "persist_sensitive_artifacts": profile.persist_sensitive_artifacts,
        "extra_sensitive_keys": extra_sensitive_keys,
        "baseline_auth": {
            "type": baseline_auth.mode,
            "config": redact_auth_config(baseline_auth_cfg if isinstance(baseline_auth_cfg, dict) else {}),
        },
        "shadow_auth": {
            "type": shadow_auth.mode,
            "config": redact_auth_config(shadow_auth_cfg if isinstance(shadow_auth_cfg, dict) else {}),
        },
        "audit": audit_record,
    }

    return SecurityRuntime(
        profile_name=profile.name,
        redact_artifacts=profile.redact_artifacts,
        persist_sensitive_artifacts=profile.persist_sensitive_artifacts,
        extra_sensitive_keys=extra_sensitive_keys,
        baseline_client=baseline_client,
        shadow_client=shadow_client,
        manifest_security=manifest_security,
    )
