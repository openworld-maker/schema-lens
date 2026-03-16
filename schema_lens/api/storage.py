"""Disk-backed storage for API jobs and artifacts."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

from schema_lens.api.errors import ArtifactNotFoundError, JobNotFoundError, UnsafePathError
from schema_lens.api.models import ApiJob
from schema_lens.util.io import ensure_dir, read_json, write_json


class JobStore(Protocol):
    def write_job(self, job_id: str, payload: dict[str, Any]) -> None: ...
    def read_job(self, job_id: str) -> dict[str, Any] | None: ...
    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        created_after: str | None = None,
    ) -> list[dict[str, Any]]: ...


class FileJobStore:
    def __init__(self, jobs_dir: Path) -> None:
        self.jobs_dir = jobs_dir

    def _job_manifest_path(self, job_id: str) -> Path:
        return self.jobs_dir / job_id / "job.json"

    def write_job(self, job_id: str, payload: dict[str, Any]) -> None:
        write_json(self._job_manifest_path(job_id), payload)

    def read_job(self, job_id: str) -> dict[str, Any] | None:
        path = self._job_manifest_path(job_id)
        if not path.exists():
            return None
        loaded = read_json(path)
        return loaded if isinstance(loaded, dict) else None

    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.jobs_dir.glob("*/job.json")):
            loaded = read_json(path)
            if not isinstance(loaded, dict):
                continue
            if status and loaded.get("status") != status:
                continue
            if job_type and loaded.get("job_type") != job_type:
                continue
            created_at = loaded.get("created_at")
            if created_after and isinstance(created_at, str) and created_at <= created_after:
                continue
            rows.append(loaded)
        rows.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return rows


class SqliteJobStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        ensure_dir(self.db_path.parent)
        self._lock = threading.Lock()
        self._connect().close()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS api_jobs (
                      job_id TEXT PRIMARY KEY,
                      status TEXT NOT NULL,
                      job_type TEXT NOT NULL,
                      created_at TEXT NOT NULL,
                      payload_json TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def write_job(self, job_id: str, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload)
        status = str(payload.get("status", ""))
        job_type = str(payload.get("job_type", ""))
        created_at = str(payload.get("created_at", ""))
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO api_jobs(job_id, status, job_type, created_at, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                      status=excluded.status,
                      job_type=excluded.job_type,
                      created_at=excluded.created_at,
                      payload_json=excluded.payload_json
                    """,
                    (job_id, status, job_type, created_at, raw),
                )
                conn.commit()
            finally:
                conn.close()

    def read_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload_json FROM api_jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return payload if isinstance(payload, dict) else None

    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        created_after: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        args: list[str] = []
        if status:
            where.append("status = ?")
            args.append(status)
        if job_type:
            where.append("job_type = ?")
            args.append(job_type)
        if created_after:
            where.append("created_at > ?")
            args.append(created_after)
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        query = f"SELECT payload_json FROM api_jobs {where_clause} ORDER BY created_at DESC"
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(query, tuple(args)).fetchall()
            finally:
                conn.close()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            loaded = json.loads(str(row["payload_json"]))
            if isinstance(loaded, dict):
                payloads.append(loaded)
        return payloads


class ApiStorage:
    def __init__(
        self,
        base_dir: Path,
        *,
        job_store_backend: str = "file",
        sqlite_path: Path | None = None,
    ) -> None:
        self.base_dir = base_dir.resolve()
        self.jobs_dir = self.base_dir / "jobs"
        self.runs_dir = self.base_dir / "runs"
        self.logs_dir = self.base_dir / "logs"
        ensure_dir(self.jobs_dir)
        ensure_dir(self.runs_dir)
        ensure_dir(self.logs_dir)
        self.job_store_backend = job_store_backend
        if job_store_backend == "sqlite":
            db_path = sqlite_path.resolve() if sqlite_path is not None else (self.base_dir / "jobs.db")
            self._job_store: JobStore = SqliteJobStore(db_path)
            self.sqlite_path = db_path
        else:
            self._job_store = FileJobStore(self.jobs_dir)
            self.sqlite_path = None

    def job_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        ensure_dir(path)
        return path

    def run_dir(self, job_id: str) -> Path:
        path = self.runs_dir / job_id
        ensure_dir(path)
        return path

    def artifacts_dir(self, job_id: str) -> Path:
        """Backward-compatible alias used by older API tests."""
        return self.run_dir(job_id)

    def job_manifest_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def request_snapshot_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "request.json"

    def artifact_manifest_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "artifacts.json"

    def write_job(self, job_id: str, payload: dict[str, Any]) -> None:
        self._job_store.write_job(job_id, payload)

    def save_job(self, job: ApiJob) -> None:
        self.write_job(job.job_id, job.model_dump())

    def read_job(self, job_id: str) -> dict[str, Any] | None:
        return self._job_store.read_job(job_id)

    def load_job(self, job_id: str) -> ApiJob:
        payload = self.read_job(job_id)
        if payload is None:
            raise JobNotFoundError(job_id)
        return ApiJob(**payload)

    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        created_after: str | None = None,
    ) -> list[ApiJob]:
        items: list[ApiJob] = []
        for loaded in self._job_store.list_jobs(
            status=status,
            job_type=job_type,
            created_after=created_after,
        ):
            if not isinstance(loaded, dict):
                continue
            job = ApiJob(**loaded)
            items.append(job)
        return items

    def write_text(self, path: Path, text: str) -> None:
        ensure_dir(path.parent)
        path.write_text(text, encoding="utf-8")

    def dump_request_snapshot(self, job_id: str, payload: dict[str, Any]) -> None:
        write_json(self.request_snapshot_path(job_id), payload)

    def read_request_snapshot(self, job_id: str) -> dict[str, Any]:
        path = self.request_snapshot_path(job_id)
        if not path.exists():
            return {}
        loaded = read_json(path)
        return loaded if isinstance(loaded, dict) else {}

    def save_artifact_manifest(self, job_id: str, manifest: dict[str, Any]) -> None:
        write_json(self.artifact_manifest_path(job_id), manifest)

    def load_artifact_manifest(self, job_id: str) -> dict[str, Any]:
        path = self.artifact_manifest_path(job_id)
        if not path.exists():
            return {}
        loaded = read_json(path)
        return loaded if isinstance(loaded, dict) else {}

    def list_artifacts_from_dir(self, root: Path) -> list[dict[str, Any]]:
        root = root.resolve()
        if not root.exists() or not root.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            rows.append(
                {
                    "name": path.name,
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                }
            )
        return rows

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        manifest = self.load_artifact_manifest(job_id)
        paths = manifest.get("paths", {})
        if isinstance(paths, dict) and paths:
            rows: list[dict[str, Any]] = []
            for name, raw_path in sorted(paths.items()):
                if not isinstance(name, str) or not isinstance(raw_path, str):
                    continue
                path = Path(raw_path)
                if path.exists() and path.is_file():
                    rows.append(
                        {
                            "name": name,
                            "path": str(path.resolve()),
                            "size_bytes": path.stat().st_size,
                        }
                    )
            if rows:
                return rows

        job = self.load_job(job_id)
        artifacts_dir = job.output_paths.get("artifacts_dir")
        if isinstance(artifacts_dir, str):
            return self.list_artifacts_from_dir(Path(artifacts_dir))
        return []

    def resolve_artifact(self, job_id: str, artifact_name: str) -> Path:
        if "/" in artifact_name or "\\" in artifact_name or ".." in artifact_name:
            raise UnsafePathError("invalid artifact name")
        artifacts = self.list_artifacts(job_id)
        for item in artifacts:
            if item.get("name") == artifact_name:
                path = Path(str(item.get("path", ""))).resolve()
                if not path.exists() or not path.is_file():
                    break
                return path
        raise ArtifactNotFoundError(artifact_name)

    def write_json_raw(self, path: Path, payload: Any) -> None:
        ensure_dir(path.parent)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
