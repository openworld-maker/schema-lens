"""Artifact listing and download routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from schema_lens.api.dependencies import get_artifact_service
from schema_lens.api.errors import ArtifactNotFoundError, JobNotFoundError, UnsafePathError
from schema_lens.api.schemas import ArtifactManifestResponse
from schema_lens.api.services.artifact_service import ArtifactService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{job_id}", response_model=ArtifactManifestResponse, summary="List artifacts for a job")
def list_artifacts(job_id: str, artifact_service: ArtifactService = Depends(get_artifact_service)) -> ArtifactManifestResponse:
    try:
        rows = artifact_service.list_artifacts(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    for row in rows:
        name = row.get("name")
        if isinstance(name, str):
            row["download_url"] = f"/artifacts/{job_id}/{name}"
    return ArtifactManifestResponse(job_id=job_id, artifacts=rows)


@router.get("/{job_id}/{artifact_name}", summary="Download artifact")
def get_artifact(
    job_id: str,
    artifact_name: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    try:
        path = artifact_service.get_artifact(job_id, artifact_name)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(path)
