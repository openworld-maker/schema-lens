"""Artifact access service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.api.errors import JobNotFoundError
from schema_lens.api.storage import ApiStorage


class ArtifactService:
    def __init__(self, storage: ApiStorage) -> None:
        self.storage = storage

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        try:
            self.storage.load_job(job_id)
        except Exception as exc:  # noqa: BLE001
            raise JobNotFoundError(job_id) from exc
        return self.storage.list_artifacts(job_id)

    def get_artifact(self, job_id: str, artifact_name: str) -> Path:
        return self.storage.resolve_artifact(job_id, artifact_name)

