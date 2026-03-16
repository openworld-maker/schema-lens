"""Internal API job models and compatibility exports."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schema_lens.api.schemas import CompareEnvRequest, GateRequest, RunCreateRequest
from schema_lens.api.schemas.common import JobStatus, JobType


class ApiJob(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    output_paths: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["ApiJob", "RunCreateRequest", "CompareEnvRequest", "GateRequest"]

