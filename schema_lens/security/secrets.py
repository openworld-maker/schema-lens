"""Secret loading helpers for security/auth config."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from schema_lens.security.errors import SecretResolutionError


ENV_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def resolve_secret(value: Any, *, env: dict[str, str] | None = None, base_dir: Path | None = None) -> str | None:
    """Resolve a secret value from inline/env/file references.

    Supports:
    - plain string values
    - "${ENV_VAR}"
    - "file:/path/to/secret.txt"
    - {"from_env": "ENV_VAR"} / {"from_file": "/path"} / {"value": "..."}
    """
    env_map = env if env is not None else os.environ

    if value is None:
        return None

    if isinstance(value, dict):
        if "from_env" in value:
            return resolve_secret(f"${{{value.get('from_env')}}}", env=env_map, base_dir=base_dir)
        if "from_file" in value:
            return resolve_secret(f"file:{value.get('from_file')}", env=env_map, base_dir=base_dir)
        if "value" in value:
            return resolve_secret(value.get("value"), env=env_map, base_dir=base_dir)
        return None

    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        raise SecretResolutionError("secret value is empty")

    env_match = ENV_PATTERN.match(raw)
    if env_match:
        var_name = env_match.group(1)
        resolved = env_map.get(var_name)
        if resolved is None or not str(resolved).strip():
            raise SecretResolutionError("required environment secret is missing or empty")
        return str(resolved).strip()

    if raw.startswith("file:"):
        path_value = raw[5:].strip()
        if not path_value:
            raise SecretResolutionError("file secret reference is empty")
        path = Path(path_value)
        if not path.is_absolute() and base_dir is not None:
            path = (base_dir / path).resolve()
        if not path.exists():
            raise SecretResolutionError("secret file does not exist")
        resolved = path.read_text(encoding="utf-8").strip()
        if not resolved:
            raise SecretResolutionError("secret file is empty")
        return resolved

    return raw


def resolve_auth_config(auth_config: dict[str, Any], *, base_dir: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve supported auth config fields into concrete runtime values."""
    resolved: dict[str, Any] = dict(auth_config)
    for field in ("username", "password", "token", "cert_file", "key_file", "ca_file"):
        current = auth_config.get(field)
        if current is not None:
            resolved[field] = resolve_secret(current, env=env, base_dir=base_dir)
        else:
            # Backward-compatible *_env/*_file keys.
            env_name = auth_config.get(f"{field}_env")
            file_ref = auth_config.get(f"{field}_file")
            if env_name:
                resolved[field] = resolve_secret(f"${{{env_name}}}", env=env, base_dir=base_dir)
            elif file_ref:
                resolved[field] = resolve_secret(f"file:{file_ref}", env=env, base_dir=base_dir)
    return resolved

def resolve_secret_field(config: dict[str, Any], field: str, *, base_dir: Path) -> str | None:
    try:
        cfg = resolve_auth_config(config, base_dir=base_dir)
        value = cfg.get(field)
        return str(value) if value is not None else None
    except SecretResolutionError:
        return None
