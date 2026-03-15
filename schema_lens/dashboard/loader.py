"""Artifact loading for dashboard views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

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


def load_run_artifacts_from_api(api_base_url: str, run_id: str) -> dict[str, Any]:
    base = api_base_url.rstrip("/")
    with httpx.Client(timeout=5.0) as client:
        overview_resp = client.get(f"{base}/dashboard/runs/{run_id}/overview")
        overview_resp.raise_for_status()
        overview = overview_resp.json()

        explorer_resp = client.get(f"{base}/dashboard/runs/{run_id}/query-explorer")
        explorer_resp.raise_for_status()
        explorer = explorer_resp.json()

    report = overview.get("report", {}) if isinstance(overview, dict) else {}
    compare = overview.get("compare", {}) if isinstance(overview, dict) else {}
    manifest = overview.get("manifest", {}) if isinstance(overview, dict) else {}
    return {
        "source": "api",
        "run_id": run_id,
        "run_manifest.json": manifest,
        "report.json": report,
        "compare.json": compare,
        "query_explorer": explorer,
    }
