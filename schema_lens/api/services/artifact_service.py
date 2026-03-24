"""Artifact access service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.api.errors import JobNotFoundError
from schema_lens.api.storage import ApiStorage
from schema_lens.security.privacy import artifact_allowed
from schema_lens.util.io import read_json


class ArtifactService:
    def __init__(self, storage: ApiStorage) -> None:
        self.storage = storage

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        try:
            job = self.storage.load_job(job_id)
        except Exception as exc:  # noqa: BLE001
            raise JobNotFoundError(job_id) from exc
        profile = self._security_profile_for_job(job_id, job)
        rows = self.storage.list_artifacts(job_id)
        return [row for row in rows if artifact_allowed(profile, str(row.get("name", "")))]

    def get_artifact(self, job_id: str, artifact_name: str) -> Path:
        try:
            job = self.storage.load_job(job_id)
        except Exception as exc:  # noqa: BLE001
            raise JobNotFoundError(job_id) from exc
        profile = self._security_profile_for_job(job_id, job)
        if not artifact_allowed(profile, artifact_name):
            raise FileNotFoundError(f"artifact '{artifact_name}' is not available under profile '{profile}'")
        return self.storage.resolve_artifact(job_id, artifact_name)

    def _security_profile_for_job(self, job_id: str, job: Any) -> str:
        output_paths = getattr(job, "output_paths", {}) or {}
        manifest_path = output_paths.get("run_manifest") or output_paths.get("manifest")
        if isinstance(manifest_path, str):
            path = Path(manifest_path)
            if path.exists():
                payload = read_json(path)
                if isinstance(payload, dict):
                    settings = payload.get("settings", {})
                    if isinstance(settings, dict):
                        security = settings.get("security", {})
                        if isinstance(security, dict):
                            profile = security.get("profile")
                            if isinstance(profile, str) and profile.strip():
                                return profile.strip().lower()

        # fallback: discover run_manifest inside tracked artifact dir
        for row in self.storage.list_artifacts(job_id):
            if row.get("name") == "run_manifest.json":
                manifest_payload = read_json(Path(str(row.get("path"))))
                if isinstance(manifest_payload, dict):
                    settings = manifest_payload.get("settings", {})
                    if isinstance(settings, dict):
                        security = settings.get("security", {})
                        if isinstance(security, dict):
                            profile = security.get("profile")
                            if isinstance(profile, str) and profile.strip():
                                return profile.strip().lower()
        return "local-dev"
