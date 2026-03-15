from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient

from schema_lens.api.app import create_api_app
from schema_lens.api.jobs import JobManager
from schema_lens.api.models import RunCreateRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.util.io import write_json


def _fake_executor(changeset_path: Path, request: RunCreateRequest, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "report.json", {"summary": {"queries_total": 1}})
    write_json(out_dir / "compare.json", {"summary": {"avg_overlap": 1.0}})


def _wait_for_status(client: TestClient, run_id: str, wanted: str, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last.get("status") == wanted:
            return last
        time.sleep(0.05)
    return last


def test_api_run_lifecycle_and_artifacts(tmp_path: Path):
    storage = ApiStorage(tmp_path)
    manager = JobManager(storage, executor=_fake_executor)
    app = create_api_app(base_dir=tmp_path, job_manager=manager)
    client = TestClient(app)

    payload = {
        "changeset_inline_yaml": "baseline:\n  solr_url: http://localhost:8983/solr\n  collection: products\n"
    }
    created = client.post("/runs", json=payload)
    assert created.status_code == 200
    run_id = created.json()["id"]

    finished = _wait_for_status(client, run_id, "succeeded")
    assert finished["status"] == "succeeded"

    artifacts = client.get(f"/runs/{run_id}/artifacts")
    assert artifacts.status_code == 200
    names = {item["name"] for item in artifacts.json()["artifacts"]}
    assert "report.json" in names

    download = client.get(f"/runs/{run_id}/artifacts/report.json")
    assert download.status_code == 200
    assert "queries_total" in download.text


def test_api_health_capabilities_and_invalid_input(tmp_path: Path):
    app = create_api_app(base_dir=tmp_path)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    caps = client.get("/capabilities")
    assert caps.status_code == 200
    assert "POST /runs" in caps.json()["endpoints"]

    bad = client.post("/runs", json={})
    assert bad.status_code == 400


def test_api_gate_endpoint(tmp_path: Path):
    app = create_api_app(base_dir=tmp_path)
    client = TestClient(app)

    compare_path = tmp_path / "compare.json"
    policy_path = tmp_path / "policy.yaml"
    write_json(compare_path, {"k": 10, "summary": {}, "diffs": []})
    policy_path.write_text("fail: []\nwarn: []\n", encoding="utf-8")

    resp = client.post(
        "/gate",
        json={"compare_path": str(compare_path), "policy_path": str(policy_path)},
    )
    assert resp.status_code == 200
    assert resp.json()["pass"] is True


def test_api_compare_env_endpoint_with_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from schema_lens.api.routes import compare_env as compare_env_route

    def fake_compare_environments(**kwargs):
        return {"replay": {"stats": {"failures": 0}}, "compare": {"summary": {"queries_total": 1}}}

    monkeypatch.setattr(compare_env_route, "compare_environments", fake_compare_environments)

    app = create_api_app(base_dir=tmp_path)
    client = TestClient(app)

    env1 = tmp_path / "env1.yaml"
    env2 = tmp_path / "env2.yaml"
    queries = tmp_path / "queries.jsonl"
    env1.write_text("name: e1\nsolr_url: http://x\ncollection: c\n", encoding="utf-8")
    env2.write_text("name: e2\nsolr_url: http://y\ncollection: c\n", encoding="utf-8")
    queries.write_text('{"params":{"q":"foo"}}\n', encoding="utf-8")

    resp = client.post(
        "/compare-env",
        json={"env1_path": str(env1), "env2_path": str(env2), "queries_path": str(queries)},
    )
    assert resp.status_code == 200
    assert Path(resp.json()["outputs"]["compare_json"]).exists()


def test_api_dashboard_endpoints(tmp_path: Path):
    storage = ApiStorage(tmp_path)
    manager = JobManager(storage, executor=_fake_executor)
    app = create_api_app(base_dir=tmp_path, job_manager=manager)
    client = TestClient(app)

    created = client.post(
        "/runs",
        json={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )
    run_id = created.json()["id"]
    finished = _wait_for_status(client, run_id, "succeeded")
    assert finished["status"] == "succeeded"

    runs = client.get("/dashboard/runs")
    assert runs.status_code == 200
    assert any(item["id"] == run_id for item in runs.json()["runs"])

    overview = client.get(f"/dashboard/runs/{run_id}/overview")
    assert overview.status_code == 200
    assert "report" in overview.json()

    explorer = client.get(f"/dashboard/runs/{run_id}/query-explorer")
    assert explorer.status_code == 200
    assert "top_regressions" in explorer.json()
