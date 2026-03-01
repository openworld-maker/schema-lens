"""Git metadata helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def current_git_commit_short(cwd: Path | None = None) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None

