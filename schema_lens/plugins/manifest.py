"""Plugin manifest helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PluginArtifactPaths:
    """Standardized output files for a plugin execution directory."""

    root: Path
    result_json: Path
    debug_json: Path
    notes_txt: Path


@dataclass
class PluginRunManifest:
    """Plugin-focused runtime metadata recorded in run manifest/report."""

    loaded_plugins: list[dict[str, Any]] = field(default_factory=list)
    failed_plugins: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    output_artifacts: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loaded_plugins": self.loaded_plugins,
            "failed_plugins": self.failed_plugins,
            "warnings": self.warnings,
            "output_artifacts": self.output_artifacts,
        }

