from pathlib import Path

import pytest

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient

from schema_lens.dashboard.app import create_dashboard_app
from schema_lens.util.io import write_json


def test_dashboard_endpoints_render(tmp_path: Path):
    write_json(
        tmp_path / "report.json",
        {
            "summary": {"queries_total": 2, "avg_overlap": 0.8, "high_risk_percent": 10.0},
            "root_causes": {"overall": [{"cause_code": "PREFIX_MATCHING_REMOVED"}]},
            "recommendations": {
                "overall": [{"recommendation_code": "USE_DUAL_FIELD_PREFIX_STRATEGY"}]
            },
        },
    )
    write_json(
        tmp_path / "compare.json",
        {"top_regressions": [{"query_id": 1}], "diffs": [{"query_id": 1}]},
    )
    client = TestClient(create_dashboard_app(tmp_path))
    html = client.get("/")
    assert html.status_code == 200
    assert "Schema-Lens Dashboard" in html.text
    overview = client.get("/api/overview")
    assert overview.status_code == 200
    explorer = client.get("/api/query-explorer")
    assert explorer.status_code == 200
    assert explorer.json()["top_regressions"][0]["query_id"] == 1
