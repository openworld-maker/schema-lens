"""Run lifecycle routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from schema_lens.api.dependencies import get_artifact_service, get_job_manager, get_run_service
from schema_lens.api.jobs import JobManager
from schema_lens.api.schemas import (
    ArtifactManifestResponse,
    JobCreatedResponse,
    JobStatusResponse,
    RunCreateRequest,
    RunStatusWithSummaryResponse,
)
from schema_lens.api.services.artifact_service import ArtifactService
from schema_lens.api.services.run_service import RunService
from schema_lens.util.io import read_json

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=JobCreatedResponse, summary="Create a new run job")
def create_run(
    payload: RunCreateRequest,
    manager: JobManager = Depends(get_job_manager),
    run_service: RunService = Depends(get_run_service),
) -> JobCreatedResponse:
    out_dir = run_service.resolve_out_dir("pending", payload)
    job = manager.submit(
        job_type="run",
        request_payload=payload.model_dump(),
        output_paths={"artifacts_dir": str(out_dir)},
        metadata=payload.metadata if isinstance(payload.metadata, dict) else {},
    )
    return JobCreatedResponse(job_id=job.job_id, id=job.job_id, status=job.status)


@router.get("/{job_id}", response_model=JobStatusResponse, summary="Get run job status")
def get_run(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobStatusResponse:
    job = manager.get(job_id)
    if job is None or job.job_type != "run":
        raise HTTPException(status_code=404, detail="run not found")
    return JobStatusResponse(**job.model_dump(), id=job.job_id)


@router.get("", summary="List run jobs")
def list_runs(
    status: str | None = None,
    created_after: str | None = None,
    manager: JobManager = Depends(get_job_manager),
) -> dict[str, object]:
    jobs = manager.list(status=status, job_type="run", created_after=created_after)
    return {"jobs": [job.model_dump() for job in jobs]}


@router.get("/{job_id}/summary", response_model=RunStatusWithSummaryResponse, summary="Get run summary")
def get_run_summary(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> RunStatusWithSummaryResponse:
    job = manager.get(job_id)
    if job is None or job.job_type != "run":
        raise HTTPException(status_code=404, detail="run not found")
    summary = job.metadata.get("summary", {}) if isinstance(job.metadata, dict) else {}
    if not isinstance(summary, dict) or not summary:
        try:
            report_path = artifact_service.get_artifact(job_id, "report.json")
            report_payload = read_json(report_path)
            if isinstance(report_payload, dict):
                report_summary = report_payload.get("summary")
                if isinstance(report_summary, dict):
                    summary = report_summary
        except Exception:  # noqa: BLE001
            summary = {}
    artifacts = artifact_service.list_artifacts(job_id)
    return RunStatusWithSummaryResponse(
        job=JobStatusResponse(**job.model_dump(), id=job.job_id),
        summary=summary if isinstance(summary, dict) else {},
        artifacts=ArtifactManifestResponse(job_id=job_id, artifacts=artifacts),
    )


@router.get("/{job_id}/artifacts", summary="Compatibility artifact list endpoint")
def list_run_artifacts(
    job_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> dict[str, object]:
    try:
        rows = artifact_service.list_artifacts(job_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="run not found") from exc
    for row in rows:
        name = row.get("name")
        if isinstance(name, str):
            row["download_url"] = f"/runs/{job_id}/artifacts/{name}"
    return {"run_id": job_id, "artifacts": rows}


@router.get("/{job_id}/artifacts/{artifact_name}", summary="Compatibility artifact download endpoint")
def get_run_artifact(
    job_id: str,
    artifact_name: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    try:
        path = artifact_service.get_artifact(job_id, artifact_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return FileResponse(path)
