"""Response schemas for run/compare/gate APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schema_lens.api.schemas.common import ArtifactManifestResponse, JobStatusResponse


class RunStatusWithSummaryResponse(BaseModel):
    job: JobStatusResponse
    summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: ArtifactManifestResponse

