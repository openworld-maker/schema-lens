"""FastAPI dashboard app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:  # pragma: no cover - exercised only when optional dep is missing.
    FASTAPI_AVAILABLE = False
    FastAPI = Any  # type: ignore[assignment]
    HTMLResponse = JSONResponse = object
else:
    FASTAPI_AVAILABLE = True

from schema_lens.dashboard.loader import load_run_artifacts


def _render_overview(artifacts: dict[str, object]) -> str:
    report_payload = artifacts.get("report.json")
    report = report_payload if isinstance(report_payload, dict) else {}
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    root_causes = report.get("root_causes", {}) if isinstance(report, dict) else {}
    recommendations = report.get("recommendations", {}) if isinstance(report, dict) else {}
    return f"""
    <html>
      <head><title>Schema-Lens Dashboard</title></head>
      <body>
        <h1>Schema-Lens Dashboard</h1>
        <h2>Overview</h2>
        <p>Queries: {summary.get("queries_total", 0)}</p>
        <p>Avg overlap: {summary.get("avg_overlap", 0)}</p>
        <p>High risk %: {summary.get("high_risk_percent", 0)}</p>
        <h2>Root Causes</h2>
        <pre>{json.dumps(root_causes, indent=2)}</pre>
        <h2>Recommendations</h2>
        <pre>{json.dumps(recommendations, indent=2)}</pre>
      </body>
    </html>
    """


def create_dashboard_app(base_path: Path) -> FastAPI:
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is required for `schema-lens serve`. Install dashboard deps.")
    app = FastAPI(title="schema-lens dashboard")

    @app.get("/", response_class=HTMLResponse)
    def overview() -> str:
        artifacts = load_run_artifacts(base_path)
        return _render_overview(artifacts)

    @app.get("/api/overview", response_class=JSONResponse)
    def api_overview() -> dict[str, object]:
        return load_run_artifacts(base_path)

    @app.get("/api/query-explorer", response_class=JSONResponse)
    def api_query_explorer() -> dict[str, object]:
        artifacts = load_run_artifacts(base_path)
        compare = artifacts.get("compare.json", {})
        return {
            "top_regressions": (
                compare.get("top_regressions", []) if isinstance(compare, dict) else []
            ),
            "diffs": compare.get("diffs", []) if isinstance(compare, dict) else [],
        }

    return app
