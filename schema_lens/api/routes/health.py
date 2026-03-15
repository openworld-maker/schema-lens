"""Health/capabilities routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok"}


@router.get("/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "service": "schema-lens-api",
        "endpoints": [
            "POST /runs",
            "GET /runs/{id}",
            "GET /runs/{id}/artifacts",
            "GET /runs/{id}/artifacts/{name}",
            "GET /dashboard/runs",
            "GET /dashboard/runs/{id}/overview",
            "GET /dashboard/runs/{id}/query-explorer",
            "POST /compare-env",
            "POST /gate",
            "GET /health",
            "GET /capabilities",
        ],
    }
