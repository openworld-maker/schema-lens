"""Background job manager for API service mode."""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import yaml

from schema_lens.api.models import ApiJob
from schema_lens.api.schemas.common import JobType
from schema_lens.api.schemas.run_requests import RunCreateRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.util.time import utc_now_iso

JobExecutor = Callable[[ApiJob], tuple[dict[str, Any], dict[str, Any]]]
LegacyRunExecutor = Callable[[Path, RunCreateRequest, Path], None]


@dataclass
class JobTask:
    job_id: str


class JobManager:
    def __init__(
        self,
        storage: ApiStorage,
        *,
        executor: JobExecutor | None = None,
        run_executor: JobExecutor | None = None,
        compare_executor: JobExecutor | None = None,
        gate_executor: JobExecutor | None = None,
        execute_inline: bool = False,
        worker_mode: Literal["inline", "inprocess", "external"] = "inprocess",
        auto_start: bool = True,
    ) -> None:
        self.storage = storage
        self.executors: dict[str, JobExecutor] = {}
        if executor is not None:
            self.executors["run"] = self._wrap_legacy_executor(executor)  # type: ignore[arg-type]
        if run_executor is not None:
            self.executors["run"] = run_executor
        if compare_executor is not None:
            self.executors["compare_env"] = compare_executor
        if gate_executor is not None:
            self.executors["gate"] = gate_executor
        self.execute_inline = execute_inline
        self.worker_mode = "inline" if execute_inline else worker_mode
        self._queue: queue.Queue[JobTask] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        if self.worker_mode == "inprocess" and auto_start:
            self.start()

    def start(self) -> None:
        if self.worker_mode != "inprocess":
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self.worker_mode != "inprocess":
            return
        self._running = False
        self._queue.put(JobTask(job_id=""))
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def _wrap_legacy_executor(self, executor: LegacyRunExecutor) -> JobExecutor:
        def _wrapped(job: ApiJob) -> tuple[dict[str, Any], dict[str, Any]]:
            payload = RunCreateRequest(**job.request_payload)
            changeset_path = self._materialize_changeset(job.job_id, payload)
            out_dir = (
                Path(payload.out_dir or payload.output_dir).resolve()
                if (payload.out_dir or payload.output_dir)
                else self.storage.run_dir(job.job_id).resolve()
            )
            executor(changeset_path, payload, out_dir)
            artifacts = self.storage.list_artifacts_from_dir(out_dir)
            self.storage.save_artifact_manifest(
                job.job_id,
                {"job_id": job.job_id, "artifacts_dir": str(out_dir), "paths": {a["name"]: a["path"] for a in artifacts}},
            )
            return {"artifacts_dir": str(out_dir), "artifacts": artifacts}, {}

        return _wrapped

    def _materialize_changeset(self, job_id: str, payload: RunCreateRequest) -> Path:
        job_dir = self.storage.job_dir(job_id)
        if payload.changeset_path:
            return Path(payload.changeset_path).resolve()
        if payload.changeset_provider:
            return Path(payload.changeset_provider).resolve()
        if payload.changeset_file_content:
            name = payload.changeset_file_name or "changeset.upload.yaml"
            path = (job_dir / name).resolve()
            self.storage.write_text(path, payload.changeset_file_content)
            return path
        if payload.changeset_inline_yaml:
            path = (job_dir / "changeset.inline.yaml").resolve()
            self.storage.write_text(path, payload.changeset_inline_yaml)
            return path
        if payload.changeset_inline_json:
            path = (job_dir / "changeset.inline.yaml").resolve()
            self.storage.write_text(path, yaml.safe_dump(payload.changeset_inline_json, sort_keys=False))
            return path
        if payload.changeset:
            path = (job_dir / "changeset.inline.yaml").resolve()
            self.storage.write_text(path, yaml.safe_dump(payload.changeset, sort_keys=False))
            return path
        raise ValueError("no changeset source found")

    def register(self, job_type: JobType, executor: JobExecutor) -> None:
        self.executors[job_type] = executor

    def submit(
        self,
        *,
        job_type: JobType,
        request_payload: dict[str, Any],
        output_paths: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApiJob:
        job_id = str(uuid.uuid4())
        job = ApiJob(
            job_id=job_id,
            job_type=job_type,
            status="queued",
            created_at=utc_now_iso(),
            request_payload=request_payload,
            output_paths=output_paths or {},
            metadata=metadata or {},
        )
        self.storage.save_job(job)
        self.storage.dump_request_snapshot(job_id, request_payload)

        if self.worker_mode == "inline":
            self._run_job(job_id)
        elif self.worker_mode == "inprocess":
            self._queue.put(JobTask(job_id=job_id))
        return job

    def get(self, job_id: str) -> ApiJob | None:
        payload = self.storage.read_job(job_id)
        if payload is None:
            return None
        return ApiJob(**payload)

    def list(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        created_after: str | None = None,
    ) -> list[ApiJob]:
        return self.storage.list_jobs(status=status, job_type=job_type, created_after=created_after)

    def _worker(self) -> None:
        while self._running:
            task = self._queue.get()
            try:
                if not task.job_id:
                    continue
                self._run_job(task.job_id)
            finally:
                self._queue.task_done()

    def run_pending(self, *, limit: int = 1) -> int:
        """Run queued jobs in pull-worker mode for future distributed workers."""
        if self.worker_mode == "inprocess":
            return 0
        ran = 0
        for job in self.list(status="queued"):
            if ran >= limit:
                break
            self._run_job(job.job_id)
            ran += 1
        return ran

    def _run_job(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        executor = self.executors.get(job.job_type)
        if executor is None:
            job.status = "failed"
            job.error = f"no executor registered for job_type={job.job_type}"
            job.ended_at = utc_now_iso()
            self.storage.save_job(job)
            return

        job.status = "running"
        job.started_at = utc_now_iso()
        self.storage.save_job(job)

        try:
            outputs, metadata = executor(job)
            job.output_paths.update(outputs)
            if isinstance(metadata, dict):
                job.metadata.update(metadata)
            job.status = "succeeded"
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)
        job.ended_at = utc_now_iso()
        self.storage.save_job(job)
