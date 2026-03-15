"""Artifact loading for dashboard views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.util.io import read_json


def load_run_artifacts(base_path: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {"base_path": str(base_path.resolve())}
    for name in (
        "run_manifest.json",
        "compare.json",
        "report.json",
        "perf_metrics.json",
        "rootcauses.json",
        "recommendations.json",
        "env_compare.json",
        "latest_monitor.json",
        "ltr_impact.json",
    ):
        file_path = base_path / name
        if file_path.exists():
            artifacts[name] = read_json(file_path)
    return artifacts
