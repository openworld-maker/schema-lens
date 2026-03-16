"""Request schemas for run/compare/gate APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class RunCreateRequest(BaseModel):
    changeset_path: str | None = None
    changeset: dict[str, Any] | None = None
    out_dir: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    # Backward-compatible aliases used by existing API tests/routes.
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

    @model_validator(mode="after")
    def validate_source(self) -> "RunCreateRequest":
        sources = [
            bool(self.changeset_path),
            bool(self.changeset),
            bool(self.changeset_inline_yaml),
            bool(self.changeset_inline_json),
            bool(self.changeset_provider),
            bool(self.changeset_file_content),
        ]
        if sum(1 for item in sources if item) != 1:
            raise ValueError("exactly one changeset source must be provided")
        return self


class CompareEnvRequest(BaseModel):
    env1: str | None = None
    env2: str | None = None
    queries_path: str
    out_dir: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    # Backward compatible names
    env1_path: str | None = None
    env2_path: str | None = None
    query_format: str = "jsonl"
    k: int = 10
    max_queries: int | None = None
    verbose: bool = False

    @model_validator(mode="after")
    def validate_paths(self) -> "CompareEnvRequest":
        env1_value = self.env1 or self.env1_path
        env2_value = self.env2 or self.env2_path
        if not env1_value or not env2_value:
            raise ValueError("env1/env2 paths are required")
        return self


class GateRequest(BaseModel):
    compare_artifact: str | None = None
    policy_path: str
    out_dir: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    # Backward compatible alias
    compare_path: str | None = None

    @model_validator(mode="after")
    def validate_compare(self) -> "GateRequest":
        if not (self.compare_artifact or self.compare_path):
            raise ValueError("compare_artifact is required")
        return self

