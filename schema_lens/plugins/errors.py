"""Plugin framework errors and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PluginError(Exception):
    """Base plugin error."""


class PluginCompatibilityError(PluginError):
    """Raised when a plugin is not compatible with current schema-lens version."""


class PluginConfigurationError(PluginError):
    """Raised when plugin configuration is invalid."""


@dataclass
class PluginIssue:
    """Structured plugin issue record for artifacts and reports."""

    plugin: str
    stage: str
    message: str
    fatal: bool = False
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "plugin": self.plugin,
            "stage": self.stage,
            "message": self.message,
            "fatal": self.fatal,
        }
        if self.details:
            payload["details"] = self.details
        return payload
