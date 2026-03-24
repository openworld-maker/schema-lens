"""Compatibility subsystem errors."""

from __future__ import annotations


class CompatibilityError(Exception):
    """Base compatibility error."""


class CapabilityProbeError(CompatibilityError):
    """Raised when runtime capability probing fails in strict contexts."""
