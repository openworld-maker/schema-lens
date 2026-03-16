"""Dashboard-focused API endpoints backed by run artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from schema_lens.api.jobs import JobManager
from schema_lens.util.io import read_json

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def _artifact_dir_for(manager: JobManager, run_id: str) -> Path:
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    artifacts = record.output_paths.get("artifacts_dir")
    if not isinstance(artifacts, str):
        raise HTTPException(status_code=404, detail="artifacts not found")
    return Path(artifacts)


@router.get("/runs")
def dashboard_runs(manager: JobManager = Depends(_manager)) -> dict[str, object]:
    records = manager.list()
    return {
        "runs": [
            {
                "id": record.job_id,
                "status": record.status,
                "created_at": record.created_at,
                "ended_at": record.ended_at,
                "error": record.error,
            }
            for record in records
        ]
    }


@router.get("/runs/{run_id}/overview")
def dashboard_overview(run_id: str, manager: JobManager = Depends(_manager)) -> dict[str, object]:
    artifact_dir = _artifact_dir_for(manager, run_id)
    report = _read_json_if_exists(artifact_dir / "report.json")
    compare = _read_json_if_exists(artifact_dir / "compare.json")
    manifest = _read_json_if_exists(artifact_dir / "run_manifest.json")
    return {
        "run_id": run_id,
        "report": report,
        "compare": {
            "summary": compare.get("summary", {}),
            "top_regressions": compare.get("top_regressions", []),
            "segments": compare.get("segments", {}),
            "privacy": compare.get("privacy", {}),
            "governance": compare.get("governance", {}),
            "observability": compare.get("observability", {}),
        },
        "manifest": manifest,
    }


@router.get("/runs/{run_id}/query-explorer")
def dashboard_query_explorer(run_id: str, manager: JobManager = Depends(_manager)) -> dict[str, object]:
    artifact_dir = _artifact_dir_for(manager, run_id)
    compare = _read_json_if_exists(artifact_dir / "compare.json")
    return {
        "run_id": run_id,
        "top_regressions": compare.get("top_regressions", []),
        "diffs": compare.get("diffs", []),
    }
