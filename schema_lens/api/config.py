"""Configuration for API service mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApiConfig:
    data_dir: Path
    local_only: bool = True
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False
    job_store_backend: str = "file"
    sqlite_path: Path | None = None
    worker_mode: str = "inprocess"
