"""API-specific errors."""

from __future__ import annotations


class ApiError(Exception):
    """Base API error."""


class JobNotFoundError(ApiError):
    """Raised when a job id is unknown."""


class ArtifactNotFoundError(ApiError):
    """Raised when a named artifact is not tracked for a job."""


class UnsafePathError(ApiError):
    """Raised when an artifact path escapes approved directories."""

