"""Gate lifecycle routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from schema_lens.api.dependencies import get_job_manager
from schema_lens.api.jobs import JobManager
from schema_lens.api.schemas import GateRequest, JobCreatedResponse, JobStatusResponse
from schema_lens.compare.gate import evaluate_gate, load_gate_policy
from schema_lens.util.io import read_json

router = APIRouter(tags=["gates"])


@router.post("/gates", response_model=JobCreatedResponse, summary="Create gate job")
def create_gate(payload: GateRequest, manager: JobManager = Depends(get_job_manager)) -> JobCreatedResponse:
    job = manager.submit(
        job_type="gate",
        request_payload=payload.model_dump(),
        output_paths={},
        metadata={},
    )
    return JobCreatedResponse(job_id=job.job_id, id=job.job_id, status=job.status)


@router.get("/gates/{job_id}", response_model=JobStatusResponse, summary="Get gate job status")
def get_gate(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobStatusResponse:
    job = manager.get(job_id)
    if job is None or job.job_type != "gate":
        raise HTTPException(status_code=404, detail="gate job not found")
    return JobStatusResponse(**job.model_dump(), id=job.job_id)


@router.post("/gate", summary="Compatibility gate endpoint")
def gate_compat(payload: GateRequest) -> dict[str, object]:
    compare_path = Path(payload.compare_artifact or payload.compare_path or "").resolve()
    policy_path = Path(payload.policy_path).resolve()
    compare_data = read_json(compare_path)
    policy_data = load_gate_policy(policy_path)
    return evaluate_gate(
        compare_data=compare_data if isinstance(compare_data, dict) else {},
        policy_data=policy_data,
        policy_dir=policy_path.parent.resolve(),
    )
