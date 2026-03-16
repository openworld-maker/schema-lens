"""Gate service orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.api.models import ApiJob
from schema_lens.api.schemas.run_requests import GateRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.compare.gate import evaluate_gate, load_gate_policy
from schema_lens.util.io import read_json, write_json


class GateService:
    def __init__(self, storage: ApiStorage) -> None:
        self.storage = storage

    def execute(self, job: ApiJob) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = GateRequest(**job.request_payload)
        compare_path = Path(payload.compare_artifact or payload.compare_path or "").resolve()
        policy_path = Path(payload.policy_path).resolve()
        out_dir = Path(payload.out_dir).resolve() if payload.out_dir else self.storage.run_dir(job.job_id)

        compare_data = read_json(compare_path)
        policy_data = load_gate_policy(policy_path)
        result = evaluate_gate(
            compare_data=compare_data if isinstance(compare_data, dict) else {},
            policy_data=policy_data,
            policy_dir=policy_path.parent.resolve(),
        )
        write_json(out_dir / "gate.json", result)

        artifacts = self.storage.list_artifacts_from_dir(out_dir)
        manifest_paths = {item["name"]: item["path"] for item in artifacts}
        self.storage.save_artifact_manifest(
            job.job_id,
            {"job_id": job.job_id, "artifacts_dir": str(out_dir), "paths": manifest_paths},
        )
        outputs = {
            "artifacts_dir": str(out_dir.resolve()),
            "gate_json": str((out_dir / "gate.json").resolve()),
            "artifacts": artifacts,
        }
        metadata = {"pass": bool(result.get("pass", False)), "metrics": result.get("metrics", {})}
        return outputs, metadata

