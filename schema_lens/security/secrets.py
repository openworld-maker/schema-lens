"""Secret loading helpers for security/auth config."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_secret_field(config: dict[str, Any], field: str, *, base_dir: Path) -> str | None:
    value = config.get(field)
    if isinstance(value, str):
        return value

    env_name = config.get(f"{field}_env")
    if isinstance(env_name, str) and env_name:
        import os

        return os.getenv(env_name)

    file_path = config.get(f"{field}_file")
    if isinstance(file_path, str) and file_path:
        path = Path(file_path)
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return path.read_text(encoding="utf-8").strip()

    return None
