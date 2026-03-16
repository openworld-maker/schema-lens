"""Compare-env lifecycle routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from schema_lens.api.dependencies import get_job_manager
from schema_lens.api.jobs import JobManager
from schema_lens.api.schemas import CompareEnvRequest, JobCreatedResponse, JobStatusResponse

router = APIRouter(prefix="/compare-env", tags=["compare-env"])


@router.post("", response_model=JobCreatedResponse, summary="Create compare-env job")
def create_compare_env(payload: CompareEnvRequest, manager: JobManager = Depends(get_job_manager)) -> JobCreatedResponse:
    job = manager.submit(
        job_type="compare_env",
        request_payload=payload.model_dump(),
        output_paths={},
        metadata={},
    )
    return JobCreatedResponse(job_id=job.job_id, id=job.job_id, status=job.status)


@router.get("/{job_id}", response_model=JobStatusResponse, summary="Get compare-env status")
def get_compare_env(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobStatusResponse:
    job = manager.get(job_id)
    if job is None or job.job_type != "compare_env":
        raise HTTPException(status_code=404, detail="compare-env job not found")
    return JobStatusResponse(**job.model_dump(), id=job.job_id)
