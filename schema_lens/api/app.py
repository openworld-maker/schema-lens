"""FastAPI app factory for solrguard API mode."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from schema_lens import __version__
from schema_lens.api.jobs import JobManager
from schema_lens.api.lifecycle import register_lifecycle_hooks
from schema_lens.api.routes.artifacts import router as artifacts_router
from schema_lens.api.routes.capabilities import router as capabilities_router
from schema_lens.api.routes.compare_env import router as compare_env_router
from schema_lens.api.routes.dashboard import router as dashboard_router
from schema_lens.api.routes.gates import router as gates_router
from schema_lens.api.routes.health import router as health_router
from schema_lens.api.routes.runs import router as runs_router
from schema_lens.api.security import (
    AllowAllRbacPolicy,
    ApiAuditLogger,
    ApiAuthProvider,
    ApiIdentity,
    ApiRbacPolicy,
    NoAuthProvider,
)
from schema_lens.api.services import ArtifactService, CompareService, GateService, RunService
from schema_lens.api.storage import ApiStorage
from schema_lens.plugins.base import BasePlugin
from schema_lens.plugins.builtin import register_builtin_plugins
from schema_lens.plugins.registry import PluginRegistry

AuthHook = Callable[[Request], None]


def _load_builtin_plugins() -> list[dict[str, object]]:
    registry = PluginRegistry()
    try:
        register_builtin_plugins(registry)
    except Exception:
        return []
    rows: list[dict[str, object]] = []
    for plugin in registry.all():
        if not isinstance(plugin, BasePlugin):
            continue
        rows.append(
            {
                "name": plugin.metadata.name,
                "version": plugin.metadata.version,
                "plugin_type": plugin.metadata.plugin_type,
                "capabilities": list(plugin.metadata.capabilities),
            }
        )
    return rows


def create_api_app(
    *,
    base_dir: Path,
    local_only: bool = True,
    auth_hook: AuthHook | None = None,
    auth_provider: ApiAuthProvider | None = None,
    rbac_policy: ApiRbacPolicy | None = None,
    audit_logger: ApiAuditLogger | None = None,
    job_store_backend: str = "file",
    sqlite_path: Path | None = None,
    worker_mode: str = "inprocess",
    job_manager: JobManager | None = None,
) -> FastAPI:
    if job_store_backend not in {"file", "sqlite"}:
        raise ValueError("job_store_backend must be one of: file, sqlite")
    if worker_mode not in {"inline", "inprocess", "external"}:
        raise ValueError("worker_mode must be one of: inline, inprocess, external")
    app = FastAPI(title="SolrGuard API", version=__version__)

    storage = ApiStorage(base_dir, job_store_backend=job_store_backend, sqlite_path=sqlite_path)
    run_service = RunService(storage)
    compare_service = CompareService(storage)
    gate_service = GateService(storage)
    artifact_service = ArtifactService(storage)

    manager = job_manager or JobManager(storage, worker_mode=worker_mode)
    if "run" not in manager.executors:
        manager.register("run", run_service.execute)
    if "compare_env" not in manager.executors:
        manager.register("compare_env", compare_service.execute)
    if "gate" not in manager.executors:
        manager.register("gate", gate_service.execute)

    app.state.storage = storage
    app.state.job_manager = manager
    app.state.run_service = run_service
    app.state.compare_service = compare_service
    app.state.gate_service = gate_service
    app.state.artifact_service = artifact_service
    app.state.local_only = local_only
    app.state.auth_hook = auth_hook
    app.state.auth_provider = auth_provider or NoAuthProvider()
    app.state.rbac_policy = rbac_policy or AllowAllRbacPolicy()
    app.state.audit_logger = audit_logger or ApiAuditLogger(storage.logs_dir / "api_audit.jsonl")
    app.state.loaded_plugins = _load_builtin_plugins()

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        identity = ApiIdentity(principal="anonymous", authenticated=False)
        logger: ApiAuditLogger = app.state.audit_logger
        if app.state.local_only:
            host = request.client.host if request.client else ""
            if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
                logger.log(
                    request=request,
                    status_code=403,
                    identity=identity,
                    outcome="denied_local_only",
                    detail="local-only mode enabled",
                )
                return JSONResponse(status_code=403, content={"detail": "local-only mode enabled"})

        provider: ApiAuthProvider = app.state.auth_provider
        try:
            identity = provider.authenticate(request)
        except HTTPException as exc:
            logger.log(
                request=request,
                status_code=exc.status_code,
                identity=identity,
                outcome="auth_failed",
                detail=str(exc.detail),
            )
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        hook = app.state.auth_hook
        if hook is not None:
            hook(request)
        policy: ApiRbacPolicy = app.state.rbac_policy
        if not policy.authorize(request, identity):
            logger.log(
                request=request,
                status_code=403,
                identity=identity,
                outcome="rbac_denied",
                detail="role policy denied request",
            )
            return JSONResponse(status_code=403, content={"detail": "forbidden"})
        response = await call_next(request)
        logger.log(
            request=request,
            status_code=response.status_code,
            identity=identity,
            outcome="ok",
        )
        return response

    register_lifecycle_hooks(app)
    app.include_router(health_router)
    app.include_router(capabilities_router)
    app.include_router(runs_router)
    app.include_router(compare_env_router)
    app.include_router(gates_router)
    app.include_router(artifacts_router)
    app.include_router(dashboard_router)
    return app
