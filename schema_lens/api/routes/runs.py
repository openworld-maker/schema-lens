"""Run submission/status/artifact routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from schema_lens.api.jobs import JobManager
from schema_lens.api.models import RunCreateRequest, RunCreateResponse, RunStatusResponse
from schema_lens.api.storage import ApiStorage

router = APIRouter(prefix="/runs", tags=["runs"])


def _manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def _storage(request: Request) -> ApiStorage:
    return request.app.state.storage


@router.post("", response_model=RunCreateResponse)
async def create_run(
    payload: RunCreateRequest,
    manager: JobManager = Depends(_manager),
) -> RunCreateResponse:
    if not any(
        [
            payload.changeset_path,
            payload.changeset_provider,
            payload.changeset_file_content,
            payload.changeset_inline_yaml,
            payload.changeset_inline_json,
        ]
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide one of changeset_path, changeset_provider, changeset_file_content, changeset_inline_yaml, or changeset_inline_json"
            ),
        )

    record = manager.submit(payload)
    return RunCreateResponse(id=record.id, status="queued")


@router.get("/{run_id}", response_model=RunStatusResponse)
def get_run(run_id: str, manager: JobManager = Depends(_manager)) -> RunStatusResponse:
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunStatusResponse(**record.to_dict())


@router.get("/{run_id}/artifacts")
def list_artifacts(
    run_id: str,
    manager: JobManager = Depends(_manager),
    storage: ApiStorage = Depends(_storage),
) -> dict[str, object]:
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")

    artifacts_dir = record.outputs.get("artifacts_dir")
    if not isinstance(artifacts_dir, str):
        return {"run_id": run_id, "artifacts": []}
    items = storage.list_artifacts_from_dir(Path(artifacts_dir))
    return {
        "run_id": run_id,
        "artifacts": [
            {
                **item,
                "download_url": f"/runs/{run_id}/artifacts/{item['name']}",
            }
            for item in items
        ],
    }


@router.get("/{run_id}/artifacts/{name}")
def download_artifact(
    run_id: str,
    name: str,
    manager: JobManager = Depends(_manager),
) -> FileResponse:
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")

    artifacts_dir = record.outputs.get("artifacts_dir")
    if not isinstance(artifacts_dir, str):
        raise HTTPException(status_code=404, detail="artifact not found")
    path = Path(artifacts_dir) / name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path)
