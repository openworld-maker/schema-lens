"""Async job manager for API run submissions."""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from schema_lens.api.models import RunCreateRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.cli import run as cli_run
from schema_lens.util.time import utc_now_iso

RunExecutor = Callable[[Path, RunCreateRequest, Path], None]


@dataclass
class JobRecord:
    id: str
    status: str
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    error: str | None = None
    request: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "request": self.request,
            "outputs": self.outputs,
        }


def default_run_executor(changeset_path: Path, request: RunCreateRequest, out_dir: Path) -> None:
    cli_run(
        changeset_path=changeset_path,
        out=out_dir,
        snapshot=None,
        k=request.k,
        cleanup=request.cleanup,
        batch_size=request.batch_size,
        scenario=request.scenario,
        enable_sensitivity=request.enable_sensitivity,
        weights=request.weights,
        vector_dimension_override=request.vector_dimension_override,
        verbose=request.verbose,
    )


class JobManager:
    def __init__(self, storage: ApiStorage, executor: RunExecutor | None = None) -> None:
        self.storage = storage
        self.executor = executor or default_run_executor
        self._queue: queue.Queue[tuple[str, RunCreateRequest, Path]] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, request: RunCreateRequest) -> JobRecord:
        job_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        record = JobRecord(
            id=job_id,
            status="queued",
            created_at=created_at,
            request=request.model_dump(),
            outputs={
                "job_manifest": str(self.storage.job_manifest_path(job_id).resolve()),
                "artifacts_dir": str(self.storage.artifacts_dir(job_id).resolve()),
            },
        )
        self.storage.write_job(job_id, record.to_dict())
        changeset_path = self._materialize_changeset(job_id, request)
        self.storage.dump_request_snapshot(job_id, request.model_dump())
        self._queue.put((job_id, request, changeset_path))
        return record

    def get(self, job_id: str) -> JobRecord | None:
        payload = self.storage.read_job(job_id)
        if payload is None:
            return None
        return JobRecord(
            id=str(payload.get("id", job_id)),
            status=str(payload.get("status", "failed")),
            created_at=str(payload.get("created_at", "")),
            started_at=payload.get("started_at"),
            ended_at=payload.get("ended_at"),
            error=payload.get("error"),
            request=payload.get("request", {}),
            outputs=payload.get("outputs", {}),
        )

    def list(self) -> list[JobRecord]:
        records: list[JobRecord] = []
        for payload in self.storage.list_jobs():
            job_id = str(payload.get("id", ""))
            if not job_id:
                continue
            records.append(
                JobRecord(
                    id=job_id,
                    status=str(payload.get("status", "failed")),
                    created_at=str(payload.get("created_at", "")),
                    started_at=payload.get("started_at"),
                    ended_at=payload.get("ended_at"),
                    error=payload.get("error"),
                    request=payload.get("request", {}),
                    outputs=payload.get("outputs", {}),
                )
            )
        return records

    def _materialize_changeset(self, job_id: str, request: RunCreateRequest) -> Path:
        job_dir = self.storage.job_dir(job_id)

        if request.changeset_path:
            return Path(request.changeset_path).resolve()

        if request.changeset_provider:
            provider_path = (Path.cwd() / request.changeset_provider).resolve()
            return provider_path

        if request.changeset_file_content:
            filename = request.changeset_file_name or "changeset.upload.yaml"
            target = job_dir / filename
            self.storage.write_text(target, request.changeset_file_content)
            return target

        inline_yaml = request.changeset_inline_yaml
        inline_json = request.changeset_inline_json

        if inline_yaml:
            target = job_dir / "changeset.inline.yaml"
            self.storage.write_text(target, inline_yaml)
            return target

        if inline_json:
            target = job_dir / "changeset.inline.yaml"
            self.storage.write_text(target, yaml.safe_dump(inline_json, sort_keys=False))
            return target

        raise ValueError(
            "One of changeset_path, changeset_provider, changeset_inline_yaml, or changeset_inline_json is required"
        )

    def _worker(self) -> None:
        while True:
            job_id, request, changeset_path = self._queue.get()
            try:
                self._run_job(job_id, request, changeset_path)
            finally:
                self._queue.task_done()

    def _run_job(self, job_id: str, request: RunCreateRequest, changeset_path: Path) -> None:
        rec = self.get(job_id)
        if rec is None:
            return

        rec.status = "running"
        rec.started_at = utc_now_iso()
        self.storage.write_job(job_id, rec.to_dict())

        artifacts_dir = (
            Path(request.output_dir).resolve()
            if request.output_dir
            else self.storage.artifacts_dir(job_id).resolve()
        )

        try:
            self.executor(changeset_path, request, artifacts_dir)
            rec.status = "succeeded"
            rec.outputs.update(
                {
                    "changeset_path": str(changeset_path.resolve()),
                    "artifacts_dir": str(artifacts_dir),
                    "artifacts": self.storage.list_artifacts_from_dir(artifacts_dir),
                }
            )
        except Exception as exc:  # noqa: BLE001
            rec.status = "failed"
            rec.error = str(exc)
        rec.ended_at = utc_now_iso()
        self.storage.write_job(job_id, rec.to_dict())
