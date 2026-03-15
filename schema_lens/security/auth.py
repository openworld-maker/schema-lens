"""Auth provider resolution for Solr HTTP clients."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schema_lens.plugins.contracts.auth import AuthProviderPlugin
from schema_lens.security.secrets import resolve_secret_field


@dataclass
class AuthMaterial:
    mode: str
    headers: dict[str, str] = field(default_factory=dict)
    cert: str | tuple[str, str] | None = None
    verify: bool | str = True


class AuthResolutionError(ValueError):
    """Raised when auth config cannot be resolved."""


def _resolve_mtls_paths(auth_cfg: dict[str, Any], *, base_dir: Path) -> tuple[str | tuple[str, str], bool | str]:
    cert_file = str(auth_cfg.get("cert_file", "")).strip()
    key_file = str(auth_cfg.get("key_file", "")).strip()
    ca_file = str(auth_cfg.get("ca_file", "")).strip()
    verify = auth_cfg.get("verify", True)

    if not cert_file:
        raise AuthResolutionError("mtls auth requires cert_file")

    cert_path = Path(cert_file)
    if not cert_path.is_absolute():
        cert_path = (base_dir / cert_path).resolve()

    if key_file:
        key_path = Path(key_file)
        if not key_path.is_absolute():
            key_path = (base_dir / key_path).resolve()
        cert: str | tuple[str, str] = (str(cert_path), str(key_path))
    else:
        cert = str(cert_path)

    verify_value: bool | str
    if isinstance(verify, bool):
        verify_value = verify
    else:
        verify_value = str(verify)

    if ca_file:
        ca_path = Path(ca_file)
        if not ca_path.is_absolute():
            ca_path = (base_dir / ca_path).resolve()
        verify_value = str(ca_path)

    return cert, verify_value


def resolve_auth_material(
    auth_cfg: dict[str, Any] | None,
    *,
    base_dir: Path,
    auth_plugins: list[AuthProviderPlugin] | None = None,
    plugin_context: dict[str, Any] | None = None,
) -> AuthMaterial:
    cfg = auth_cfg if isinstance(auth_cfg, dict) else {}
    mode = str(cfg.get("type", "none")).strip().lower()

    if mode in {"", "none"}:
        return AuthMaterial(mode="none")

    if mode == "basic":
        username = resolve_secret_field(cfg, "username", base_dir=base_dir)
        password = resolve_secret_field(cfg, "password", base_dir=base_dir)
        if username is None or password is None:
            raise AuthResolutionError("basic auth requires username and password")
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return AuthMaterial(mode="basic", headers={"Authorization": f"Basic {token}"})

    if mode == "bearer":
        token = resolve_secret_field(cfg, "token", base_dir=base_dir)
        if token is None:
            raise AuthResolutionError("bearer auth requires token")
        return AuthMaterial(mode="bearer", headers={"Authorization": f"Bearer {token}"})

    if mode == "mtls":
        cert, verify = _resolve_mtls_paths(cfg, base_dir=base_dir)
        return AuthMaterial(mode="mtls", cert=cert, verify=verify)

    if mode in {"plugin", "kerberos"}:
        plugin_name = str(cfg.get("provider", "")).strip()
        if not plugin_name:
            raise AuthResolutionError(f"{mode} auth requires provider plugin name")
        for plugin in auth_plugins or []:
            if plugin.metadata.name != plugin_name:
                continue
            payload = plugin.build_auth(plugin_context or {})
            if not isinstance(payload, dict):
                raise AuthResolutionError(f"auth plugin '{plugin_name}' returned non-dict")
            headers = payload.get("headers", {})
            if not isinstance(headers, dict):
                headers = {}
            cert = payload.get("cert")
            verify = payload.get("verify", True)
            return AuthMaterial(
                mode=mode,
                headers={str(k): str(v) for k, v in headers.items()},
                cert=cert if isinstance(cert, (str, tuple)) else None,
                verify=verify if isinstance(verify, (bool, str)) else True,
            )
        raise AuthResolutionError(f"auth plugin not found: {plugin_name}")

    raise AuthResolutionError(f"unsupported auth type: {mode}")
