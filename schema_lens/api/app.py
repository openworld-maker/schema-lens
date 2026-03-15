"""FastAPI app factory for schema-lens API mode."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from schema_lens.api.jobs import JobManager
from schema_lens.api.routes.compare_env import router as compare_env_router
from schema_lens.api.routes.dashboard import router as dashboard_router
from schema_lens.api.routes.gates import router as gates_router
from schema_lens.api.routes.health import router as health_router
from schema_lens.api.routes.runs import router as runs_router
from schema_lens.api.storage import ApiStorage

AuthHook = Callable[[Request], None]


def create_api_app(
    *,
    base_dir: Path,
    local_only: bool = True,
    auth_hook: AuthHook | None = None,
    job_manager: JobManager | None = None,
) -> FastAPI:
    app = FastAPI(title="schema-lens api", version="0.2.0")

    storage = ApiStorage(base_dir)
    app.state.storage = storage
    app.state.job_manager = job_manager or JobManager(storage)
    app.state.local_only = local_only
    app.state.auth_hook = auth_hook

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        if app.state.local_only:
            host = request.client.host if request.client else ""
            if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
                return JSONResponse(status_code=403, content={"detail": "local-only mode enabled"})
        hook = app.state.auth_hook
        if hook is not None:
            hook(request)
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(runs_router)
    app.include_router(dashboard_router)
    app.include_router(compare_env_router)
    app.include_router(gates_router)
    return app
