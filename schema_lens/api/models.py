"""Pydantic request/response models for API mode."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    changeset_path: str | None = None
    changeset_inline_yaml: str | None = None
    changeset_inline_json: dict[str, Any] | None = None
    changeset_provider: str | None = None
    changeset_file_content: str | None = None
    changeset_file_name: str | None = None
    output_dir: str | None = None
    k: int | None = None
    cleanup: bool | None = None
    batch_size: int = 100
    scenario: list[str] | None = None
    enable_sensitivity: bool | None = None
    weights: str | None = None
    vector_dimension_override: int | None = None
    verbose: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreateResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed"]


class RunStatusResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    error: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class CompareEnvRequest(BaseModel):
    env1_path: str
    env2_path: str
    queries_path: str
    query_format: str = "jsonl"
    k: int = 10
    max_queries: int | None = None
    verbose: bool = False
    out_dir: str | None = None


class GateRequest(BaseModel):
    compare_path: str
    policy_path: str
