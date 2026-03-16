"""Plugin framework errors and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PluginError(Exception):
    """Base plugin error."""


class PluginCompatibilityError(PluginError):
    """Raised when a plugin is not compatible with current SolrGuard version."""


class PluginConfigurationError(PluginError):
    """Raised when plugin configuration is invalid."""


class PluginExecutionError(PluginError):
    """Raised when a plugin fails during a run phase."""


@dataclass
class PluginIssue:
    """Structured plugin issue record for artifacts and reports."""

    plugin: str
    stage: str
    message: str
    plugin_type: str | None = None
    fatal: bool = False
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "plugin": self.plugin,
            "stage": self.stage,
            "message": self.message,
            "fatal": self.fatal,
        }
        if self.plugin_type:
            payload["plugin_type"] = self.plugin_type
        if self.details:
            payload["details"] = self.details
        return payload
