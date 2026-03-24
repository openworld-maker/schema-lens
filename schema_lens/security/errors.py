"""Security-specific errors."""

from __future__ import annotations


class SecurityConfigError(ValueError):
    """Raised when security configuration is invalid."""


class SecretResolutionError(SecurityConfigError):
    """Raised when a required secret cannot be resolved safely."""


class AuthProviderError(SecurityConfigError):
    """Raised when auth provider configuration fails."""
