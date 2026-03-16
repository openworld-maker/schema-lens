"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Request

from schema_lens.api.jobs import JobManager
from schema_lens.api.services import ArtifactService, CompareService, GateService, RunService
from schema_lens.api.storage import ApiStorage


def get_storage(request: Request) -> ApiStorage:
    return request.app.state.storage


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def get_run_service(request: Request) -> RunService:
    return request.app.state.run_service


def get_compare_service(request: Request) -> CompareService:
    return request.app.state.compare_service


def get_gate_service(request: Request) -> GateService:
    return request.app.state.gate_service


def get_artifact_service(request: Request) -> ArtifactService:
    return request.app.state.artifact_service

