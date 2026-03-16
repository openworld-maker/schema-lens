"""Common API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobType = Literal["run", "compare_env", "gate"]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "solrguard-api"
    version: str


class ArtifactItem(BaseModel):
    name: str
    path: str
    size_bytes: int
    download_url: str | None = None


class ArtifactManifestResponse(BaseModel):
    job_id: str
    artifacts: list[ArtifactItem] = Field(default_factory=list)


class JobCreatedResponse(BaseModel):
    job_id: str
    id: str | None = None
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    id: str | None = None
    job_type: JobType
    status: JobStatus
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    output_paths: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class CapabilitiesResponse(BaseModel):
    service: str = "solrguard-api"
    version: str
    features: list[str] = Field(default_factory=list)
    plugin_types: list[str] = Field(default_factory=list)
    loaded_plugins: list[dict[str, Any]] = Field(default_factory=list)
    solr_hints: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
