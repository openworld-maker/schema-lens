"""Disk-backed storage for API jobs and artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.util.io import ensure_dir, read_json, write_json


class ApiStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()
        self.jobs_dir = self.base_dir / "jobs"
        ensure_dir(self.jobs_dir)

    def job_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        ensure_dir(path)
        return path

    def artifacts_dir(self, job_id: str) -> Path:
        path = self.job_dir(job_id) / "artifacts"
        ensure_dir(path)
        return path

    def job_manifest_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        ensure_dir(path.parent)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        write_json(tmp_path, payload)
        tmp_path.replace(path)

    def write_job(self, job_id: str, payload: dict[str, Any]) -> None:
        self._write_json_atomic(self.job_manifest_path(job_id), payload)

    def read_job(self, job_id: str) -> dict[str, Any] | None:
        path = self.job_manifest_path(job_id)
        if not path.exists():
            return None
        loaded = read_json(path)
        return loaded if isinstance(loaded, dict) else None

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        return self.list_artifacts_from_dir(self.artifacts_dir(job_id))

    def list_artifacts_from_dir(self, root: Path) -> list[dict[str, Any]]:
        root = root.resolve()
        results: list[dict[str, Any]] = []
        for path in sorted(root.glob("*")):
            if path.is_file():
                results.append(
                    {
                        "name": path.name,
                        "path": str(path.resolve()),
                        "size_bytes": path.stat().st_size,
                    }
                )
        return results

    def write_text(self, path: Path, text: str) -> None:
        ensure_dir(path.parent)
        path.write_text(text, encoding="utf-8")

    def write_json_path(self, path: Path, payload: dict[str, Any]) -> None:
        write_json(path, payload)

    def dump_request_snapshot(self, job_id: str, payload: dict[str, Any]) -> None:
        path = self.job_dir(job_id) / "request.json"
        self.write_json_path(path, payload)

    def read_request_snapshot(self, job_id: str) -> dict[str, Any]:
        path = self.job_dir(job_id) / "request.json"
        if not path.exists():
            return {}
        loaded = read_json(path)
        return loaded if isinstance(loaded, dict) else {}

    def read_json_file(self, path: Path) -> dict[str, Any]:
        loaded = read_json(path)
        return loaded if isinstance(loaded, dict) else {}

    def write_json_raw(self, path: Path, payload: Any) -> None:
        ensure_dir(path.parent)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        for path in sorted(self.jobs_dir.glob("*/job.json")):
            loaded = read_json(path)
            if isinstance(loaded, dict):
                jobs.append(loaded)
        jobs.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return jobs
