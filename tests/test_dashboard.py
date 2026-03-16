from pathlib import Path
import time

import pytest

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient

from schema_lens.api.app import create_api_app
from schema_lens.api.jobs import JobManager
from schema_lens.api.models import RunCreateRequest
from schema_lens.api.storage import ApiStorage
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
    assert "SolrGuard Dashboard" in html.text
    overview = client.get("/api/overview")
    assert overview.status_code == 200
    explorer = client.get("/api/query-explorer")
    assert explorer.status_code == 200
    assert explorer.json()["top_regressions"][0]["query_id"] == 1


def test_dashboard_api_backed_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_executor(changeset_path: Path, request: RunCreateRequest, out_dir: Path) -> None:
        write_json(
            out_dir / "report.json",
            {
                "summary": {"queries_total": 3, "avg_overlap": 0.7, "high_risk_percent": 5.0},
                "root_causes": {"overall": []},
                "recommendations": {"overall": []},
            },
        )
        write_json(out_dir / "compare.json", {"top_regressions": [{"query_id": 99}], "diffs": []})
        write_json(out_dir / "run_manifest.json", {"run_id": "x"})

    storage = ApiStorage(tmp_path / "api")
    manager = JobManager(storage, executor=fake_executor)
    api_client = TestClient(create_api_app(base_dir=tmp_path / "api", job_manager=manager))
    created = api_client.post(
        "/runs",
        json={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )
    run_id = created.json()["id"]
    for _ in range(50):
        state = api_client.get(f"/runs/{run_id}").json()
        if state["status"] == "succeeded":
            break
        time.sleep(0.02)

    def fake_remote_loader(api_base_url: str, run_id_value: str):
        overview = api_client.get(f"/dashboard/runs/{run_id_value}/overview").json()
        explorer = api_client.get(f"/dashboard/runs/{run_id_value}/query-explorer").json()
        return {
            "source": "api",
            "run_id": run_id_value,
            "run_manifest.json": overview.get("manifest", {}),
            "report.json": overview.get("report", {}),
            "compare.json": overview.get("compare", {}),
            "query_explorer": explorer,
        }

    monkeypatch.setattr("schema_lens.dashboard.app.load_run_artifacts_from_api", fake_remote_loader)
    app = create_dashboard_app(api_base_url=str(api_client.base_url).rstrip("/"), run_id=run_id)
    client = TestClient(app)
    html = client.get("/")
    assert html.status_code == 200
    overview = client.get("/api/overview")
    assert overview.status_code == 200
    explorer = client.get("/api/query-explorer")
    assert explorer.status_code == 200
    assert explorer.json()["top_regressions"][0]["query_id"] == 99
