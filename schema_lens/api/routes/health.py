"""Health routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from schema_lens import __version__
from schema_lens.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
def health() -> HealthResponse:
    return HealthResponse(version=__version__)


@router.get("/health/details", summary="Detailed health and storage info")
def health_details(request: Request) -> dict[str, object]:
    storage = request.app.state.storage
    manager = request.app.state.job_manager
    plugins = request.app.state.loaded_plugins if hasattr(request.app.state, "loaded_plugins") else []
    return {
        "status": "ok",
        "service": "solrguard-api",
        "version": __version__,
        "storage_dir": str(storage.base_dir),
        "jobs_dir": str(storage.jobs_dir),
        "runs_dir": str(storage.runs_dir),
        "job_store_backend": storage.job_store_backend,
        "sqlite_path": str(storage.sqlite_path) if storage.sqlite_path is not None else None,
        "worker_mode": getattr(manager, "worker_mode", "inprocess"),
        "plugin_count": len(plugins) if isinstance(plugins, list) else 0,
    }
