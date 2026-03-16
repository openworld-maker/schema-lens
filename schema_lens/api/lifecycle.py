"""Lifespan hooks for API service mode."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def api_lifespan(app: FastAPI):
    manager = getattr(app.state, "job_manager", None)
    if manager is not None and hasattr(manager, "start"):
        manager.start()
    try:
        yield
    finally:
        if manager is not None and hasattr(manager, "stop"):
            manager.stop()


def register_lifecycle_hooks(app: FastAPI) -> FastAPI:
    app.router.lifespan_context = api_lifespan
    return app
