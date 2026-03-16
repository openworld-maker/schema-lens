"""Plugin SDK base contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PluginMetadata:
    """Static plugin metadata used for discovery and compatibility checks."""

    name: str
    version: str
    plugin_type: str
    description: str = ""
    compatible_schema_lens_version: str = "*"
    schema_lens_version: str | None = None
    capabilities: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.schema_lens_version and self.compatible_schema_lens_version == "*":
            object.__setattr__(self, "compatible_schema_lens_version", self.schema_lens_version)


@dataclass
class PluginContext:
    """Mutable execution context passed to plugin lifecycle hooks."""

    run_id: str
    out_dir: Path
    changeset_path: Path
    changeset: dict[str, Any]
    manifest: dict[str, Any]
    strict: bool = False
    phase: str = "finalize"
    plugin_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        config = self.plugin_configs.get(plugin_name, {})
        return config if isinstance(config, dict) else {}


@dataclass
class PluginResult:
    """Normalized plugin execution result."""

    plugin: str
    plugin_type: str
    status: str
    phase: str
    optional: bool = True
    capabilities: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    artifact_dir: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "plugin": self.plugin,
            "plugin_type": self.plugin_type,
            "status": self.status,
            "phase": self.phase,
            "optional": self.optional,
            "capabilities": self.capabilities,
            "outputs": self.outputs,
            "warnings": self.warnings,
        }
        if self.artifact_dir:
            payload["artifact_dir"] = self.artifact_dir
        if self.error:
            payload["error"] = self.error
        return payload


class BasePlugin:
    """Base class for all SolrGuard plugins."""

    metadata: PluginMetadata
    required: bool = False

    def get_name(self) -> str:
        return self.metadata.name

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate plugin-specific configuration from changeset.plugins.config."""

    def redact(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return safe configuration for manifests/logs."""
        return dict(config)

    def validate(self, context: PluginContext) -> None:
        """Validate plugin configuration and dependencies before execution."""

    def initialize(self, context: PluginContext) -> None:
        """Initialize resources before execution."""

    def execute(self, context: PluginContext, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute plugin logic and return JSON-serializable outputs."""
        return {}

    def cleanup(self, context: PluginContext) -> None:
        """Release resources after execution."""
