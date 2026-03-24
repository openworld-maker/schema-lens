"""Run service orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from schema_lens.api.models import ApiJob
from schema_lens.api.schemas.run_requests import RunCreateRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.cli import run as cli_run
from schema_lens.security.redaction import redact_dict
from schema_lens.util.io import read_json


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_dict(payload)
    return redacted if isinstance(redacted, dict) else payload


class RunService:
    def __init__(self, storage: ApiStorage) -> None:
        self.storage = storage

    def normalize_request(self, payload: RunCreateRequest) -> dict[str, Any]:
        return _redact_payload(payload.model_dump())

    def materialize_changeset(self, job_id: str, payload: RunCreateRequest) -> Path:
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

    def resolve_out_dir(self, job_id: str, payload: RunCreateRequest) -> Path:
        out_dir = payload.out_dir or payload.output_dir
        if out_dir:
            return Path(out_dir).resolve()
        return self.storage.run_dir(job_id).resolve()

    def execute(self, job: ApiJob) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = RunCreateRequest(**job.request_payload)
        changeset_path = self.materialize_changeset(job.job_id, payload)
        out_dir = self.resolve_out_dir(job.job_id, payload)

        options = payload.options if isinstance(payload.options, dict) else {}
        cli_run(
            changeset_path=changeset_path,
            out=out_dir,
            snapshot=None,
            k=payload.k if payload.k is not None else options.get("k"),
            cleanup=payload.cleanup if payload.cleanup is not None else options.get("cleanup"),
            batch_size=int(options.get("batch_size", payload.batch_size)),
            scenario=payload.scenario if payload.scenario is not None else options.get("scenario"),
            enable_sensitivity=(
                payload.enable_sensitivity
                if payload.enable_sensitivity is not None
                else options.get("enable_sensitivity")
            ),
            weights=payload.weights if payload.weights is not None else options.get("weights"),
            vector_dimension_override=(
                payload.vector_dimension_override
                if payload.vector_dimension_override is not None
                else options.get("vector_dimension_override")
            ),
            verbose=bool(options.get("verbose", payload.verbose)),
        )

        artifacts = self.storage.list_artifacts_from_dir(out_dir)
        manifest_paths = {item["name"]: item["path"] for item in artifacts}
        self.storage.save_artifact_manifest(
            job.job_id,
            {"job_id": job.job_id, "artifacts_dir": str(out_dir), "paths": manifest_paths},
        )

        summary: dict[str, Any] = {}
        compatibility: dict[str, Any] = {}
        report_json_path = out_dir / "report.json"
        if report_json_path.exists():
            report = read_json(report_json_path)
            if isinstance(report, dict):
                summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
                compatibility = (
                    report.get("compatibility", {}) if isinstance(report.get("compatibility"), dict) else {}
                )

        outputs = {
            "changeset_path": str(changeset_path),
            "artifacts_dir": str(out_dir),
            "artifacts": artifacts,
            "report_json": str((out_dir / "report.json").resolve()),
            "report_html": str((out_dir / "report.html").resolve()),
        }
        metadata = {
            "summary": summary,
            "compatibility": {
                "solr_version": compatibility.get("solr_version"),
                "support_tier": compatibility.get("support_tier"),
                "confidence": compatibility.get("confidence"),
                "missing_capabilities": compatibility.get("missing_capabilities", []),
            },
        }
        return outputs, metadata
