from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.api.errors import ArtifactNotFoundError, UnsafePathError
from schema_lens.api.models import ApiJob
from schema_lens.api.storage import ApiStorage
from schema_lens.util.time import utc_now_iso


def _job(job_id: str) -> ApiJob:
    return ApiJob(
        job_id=job_id,
        job_type="run",
        status="queued",
        created_at=utc_now_iso(),
        output_paths={},
    )


def test_storage_save_load_list_and_manifest(tmp_path: Path) -> None:
    storage = ApiStorage(tmp_path)
    job = _job("j1")
    storage.save_job(job)
    loaded = storage.load_job("j1")
    assert loaded.job_id == "j1"
    assert storage.list_jobs()[0].job_id == "j1"

    run_dir = storage.run_dir("j1")
    artifact = run_dir / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    storage.save_artifact_manifest(
        "j1",
        {"job_id": "j1", "artifacts_dir": str(run_dir), "paths": {"report.json": str(artifact)}},
    )
    rows = storage.list_artifacts("j1")
    assert rows[0]["name"] == "report.json"


def test_storage_path_traversal_protection(tmp_path: Path) -> None:
    storage = ApiStorage(tmp_path)
    job = _job("j1")
    run_dir = storage.run_dir("j1")
    artifact = run_dir / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    job.output_paths = {"artifacts_dir": str(run_dir)}
    storage.save_job(job)
    storage.save_artifact_manifest(
        "j1",
        {"job_id": "j1", "artifacts_dir": str(run_dir), "paths": {"report.json": str(artifact)}},
    )

    with pytest.raises(UnsafePathError):
        storage.resolve_artifact("j1", "../etc/passwd")
    with pytest.raises(ArtifactNotFoundError):
        storage.resolve_artifact("j1", "missing.json")


def test_storage_sqlite_job_backend(tmp_path: Path) -> None:
    storage = ApiStorage(tmp_path, job_store_backend="sqlite")
    job = _job("sqlite-j1")
    storage.save_job(job)
    loaded = storage.load_job("sqlite-j1")
    assert loaded.job_id == "sqlite-j1"
    listed = storage.list_jobs()
    assert listed and listed[0].job_id == "sqlite-j1"
    assert storage.sqlite_path is not None and storage.sqlite_path.exists()
