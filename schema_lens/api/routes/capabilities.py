"""Capabilities and plugin routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from schema_lens import __version__
from schema_lens.api.schemas import CapabilitiesResponse

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities", response_model=CapabilitiesResponse, summary="Service capabilities")
def capabilities(request: Request) -> CapabilitiesResponse:
    loaded_plugins = request.app.state.loaded_plugins if hasattr(request.app.state, "loaded_plugins") else []
    plugin_types = sorted({item.get("plugin_type", "") for item in loaded_plugins if isinstance(item, dict)})
    storage = request.app.state.storage
    manager = request.app.state.job_manager
    return CapabilitiesResponse(
        version=__version__,
        features=[
            "runs",
            "compare_env",
            "gates",
            "artifacts",
            "dashboard",
            "health",
            "plugins",
            "rbac",
            "audit_trail",
        ],
        plugin_types=[value for value in plugin_types if value],
        loaded_plugins=loaded_plugins if isinstance(loaded_plugins, list) else [],
        solr_hints={
            "compatibility_probe": "/admin/info/system",
            "supported_versions": ["8.x", "9.x", "10.x"],
        },
        security={
            "local_only": bool(getattr(request.app.state, "local_only", True)),
            "auth_provider": type(getattr(request.app.state, "auth_provider", object())).__name__,
            "rbac_policy": type(getattr(request.app.state, "rbac_policy", object())).__name__,
        },
        execution={
            "job_store_backend": storage.job_store_backend,
            "sqlite_path": str(storage.sqlite_path) if storage.sqlite_path is not None else None,
            "worker_mode": getattr(manager, "worker_mode", "inprocess"),
        },
    )


@router.get("/plugins", summary="Loaded plugin inventory")
def plugins(request: Request) -> dict[str, object]:
    loaded_plugins = request.app.state.loaded_plugins if hasattr(request.app.state, "loaded_plugins") else []
    return {"plugins": loaded_plugins if isinstance(loaded_plugins, list) else []}
