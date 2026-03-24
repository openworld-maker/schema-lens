"""Auth provider resolution for Solr HTTP clients."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.plugins.contracts.auth import AuthProviderPlugin
from schema_lens.security.auth_models import AuthMaterial
from schema_lens.security.errors import AuthProviderError
from schema_lens.security.providers.basic_auth import build_basic_auth
from schema_lens.security.providers.bearer_auth import build_bearer_auth
from schema_lens.security.providers.mtls_auth import build_mtls_auth
from schema_lens.security.providers.none_auth import build_none_auth
from schema_lens.security.secrets import resolve_auth_config


class AuthResolutionError(AuthProviderError):
    """Raised when auth config cannot be resolved."""


def resolve_auth_material(
    auth_cfg: dict[str, Any] | None,
    *,
    base_dir: Path,
    auth_plugins: list[AuthProviderPlugin] | None = None,
    plugin_context: dict[str, Any] | None = None,
) -> AuthMaterial:
    cfg = auth_cfg if isinstance(auth_cfg, dict) else {}
    mode = str(cfg.get("type", "none")).strip().lower()
    resolved = resolve_auth_config(cfg, base_dir=base_dir)

    if mode in {"", "none"}:
        return build_none_auth()

    if mode == "basic":
        username = resolved.get("username")
        password = resolved.get("password")
        if not username or not password:
            raise AuthResolutionError("basic auth requires non-empty username and password")
        return build_basic_auth(str(username), str(password))

    if mode == "bearer":
        token = resolved.get("token")
        if not token:
            raise AuthResolutionError("bearer auth requires non-empty token")
        return build_bearer_auth(str(token))

    if mode == "mtls":
        cert_file = resolved.get("cert_file")
        key_file = resolved.get("key_file")
        ca_file = resolved.get("ca_file")
        verify = cfg.get("verify", True)
        if not cert_file:
            raise AuthResolutionError("mtls auth requires cert_file")
        try:
            return build_mtls_auth(
                cert_file=str(cert_file),
                key_file=str(key_file) if key_file else None,
                ca_file=str(ca_file) if ca_file else None,
                base_dir=base_dir,
                verify=verify if isinstance(verify, (bool, str)) else True,
            )
        except AuthProviderError as exc:
            raise AuthResolutionError(str(exc)) from exc

    if mode == "plugin":
        plugin_name = str(cfg.get("provider", "")).strip()
        if not plugin_name:
            raise AuthResolutionError("plugin auth requires provider plugin name")
        plugin_cfg = cfg.get("plugin_config", {})
        if not isinstance(plugin_cfg, dict):
            plugin_cfg = {}
        for plugin in auth_plugins or []:
            if plugin.metadata.name != plugin_name:
                continue
            plugin.validate_config(plugin_cfg)
            payload = plugin.build_request_auth(plugin_cfg, plugin_context or {})
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
