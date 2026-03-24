from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient

from schema_lens.api.app import create_api_app
from schema_lens.api.jobs import JobManager
from schema_lens.api.models import ApiJob, RunCreateRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.api.services.run_service import RunService
from schema_lens.util.io import write_json


def _fake_run_executor(changeset_path: Path, request: RunCreateRequest, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        out_dir / "report.json",
        {
            "summary": {"queries_total": 1, "high_risk_percent": 0.0},
            "compatibility": {
                "solr_version": "9.7.0",
                "support_tier": "recommended",
                "confidence": "high",
                "missing_capabilities": [],
            },
        },
    )
    write_json(out_dir / "report.html", {"ok": True})
    write_json(out_dir / "compare.json", {"summary": {"avg_overlap": 1.0}, "diffs": []})
    write_json(
        out_dir / "run_manifest.json",
        {"settings": {"security": {"profile": "local-dev"}}},
    )


def _fake_compare_executor(job: ApiJob) -> tuple[dict, dict]:
    out_dir = Path(job.output_paths.get("artifacts_dir", Path.cwd())).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "compare.json", {"summary": {"queries_total": 2}})
    return {"artifacts_dir": str(out_dir), "artifacts": [{"name": "compare.json", "path": str(out_dir / "compare.json"), "size_bytes": (out_dir / "compare.json").stat().st_size}]}, {"summary": {"queries_total": 2}}


def _fake_gate_executor(job: ApiJob) -> tuple[dict, dict]:
    out_dir = Path(job.output_paths.get("artifacts_dir", Path.cwd())).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "gate.json", {"pass": True, "failed_rules": [], "warned_rules": []})
    return {"artifacts_dir": str(out_dir), "artifacts": [{"name": "gate.json", "path": str(out_dir / "gate.json"), "size_bytes": (out_dir / "gate.json").stat().st_size}]}, {"pass": True}


def _wait_for_status(
    client: TestClient,
    url: str,
    wanted: str,
    timeout_s: float = 5.0,
) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        resp = client.get(url)
        assert resp.status_code == 200
        last = resp.json()
        if last.get("status") == wanted:
            return last
        time.sleep(0.05)
    return last


def _app_with_fakes(tmp_path: Path) -> TestClient:
    storage = ApiStorage(tmp_path)
    manager = JobManager(
        storage,
        executor=_fake_run_executor,
        compare_executor=_fake_compare_executor,
        gate_executor=_fake_gate_executor,
    )
    app = create_api_app(base_dir=tmp_path, job_manager=manager)
    return TestClient(app)


def test_health_and_capabilities(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)
    assert client.get("/health").status_code == 200
    assert client.get("/health/details").status_code == 200
    caps = client.get("/capabilities")
    assert caps.status_code == 200
    payload = caps.json()
    assert payload["service"] == "solrguard-api"
    assert "runs" in payload["features"]
    assert "vector_supported" in payload["solr_hints"]["capability_flags"]
    assert client.get("/plugins").status_code == 200


def test_run_service_metadata_includes_compatibility(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = ApiStorage(tmp_path)
    service = RunService(storage)
    job = ApiJob(
        job_id="job-1",
        job_type="run",
        status="queued",
        created_at="2026-01-01T00:00:00Z",
        request_payload={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )

    def _fake_cli_run(**kwargs: object) -> None:
        out_dir = Path(str(kwargs["out"]))
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            out_dir / "report.json",
            {
                "summary": {"queries_total": 1},
                "compatibility": {"solr_version": "9.7.0", "support_tier": "recommended", "confidence": "high"},
            },
        )
        write_json(out_dir / "report.html", {"ok": True})
        write_json(out_dir / "compare.json", {"summary": {"avg_overlap": 1.0}})

    monkeypatch.setattr("schema_lens.api.services.run_service.cli_run", _fake_cli_run)
    _, metadata = service.execute(job)
    assert metadata["compatibility"]["support_tier"] == "recommended"


def test_post_runs_and_get_status_and_summary(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)
    created = client.post(
        "/runs",
        json={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    status_payload = _wait_for_status(client, f"/runs/{job_id}", "succeeded")
    assert status_payload["status"] == "succeeded"
    summary = client.get(f"/runs/{job_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["summary"]["queries_total"] == 1


def test_artifact_endpoints_and_compat_paths(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)
    created = client.post(
        "/runs",
        json={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )
    job_id = created.json()["job_id"]
    _wait_for_status(client, f"/runs/{job_id}", "succeeded")

    artifacts = client.get(f"/artifacts/{job_id}")
    assert artifacts.status_code == 200
    names = {item["name"] for item in artifacts.json()["artifacts"]}
    assert "report.json" in names

    download = client.get(f"/artifacts/{job_id}/report.json")
    assert download.status_code == 200

    compat_list = client.get(f"/runs/{job_id}/artifacts")
    assert compat_list.status_code == 200
    compat_download = client.get(f"/runs/{job_id}/artifacts/report.json")
    assert compat_download.status_code == 200


def test_compare_env_and_gates_job_lifecycle(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)

    compare_created = client.post(
        "/compare-env",
        json={"env1": "examples/envs/prod_us.yaml", "env2": "examples/envs/prod_eu.yaml", "queries_path": "examples/queries/env_compare_queries.jsonl"},
    )
    assert compare_created.status_code == 200
    compare_job_id = compare_created.json()["job_id"]
    compare_status = _wait_for_status(client, f"/compare-env/{compare_job_id}", "succeeded")
    assert compare_status["status"] == "succeeded"

    gate_created = client.post(
        "/gates",
        json={"compare_artifact": "out/demo/compare.json", "policy_path": "examples/policy/gate_default.yaml"},
    )
    assert gate_created.status_code == 200
    gate_job_id = gate_created.json()["job_id"]
    gate_status = _wait_for_status(client, f"/gates/{gate_job_id}", "succeeded")
    assert gate_status["status"] == "succeeded"


def test_invalid_payload_and_path_traversal(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)
    bad_run = client.post("/runs", json={})
    assert bad_run.status_code == 422

    created = client.post(
        "/runs",
        json={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )
    job_id = created.json()["job_id"]
    _wait_for_status(client, f"/runs/{job_id}", "succeeded")
    traversal = client.get(f"/artifacts/{job_id}/../secret.txt")
    assert traversal.status_code in {400, 404}


def test_gate_compat_endpoint(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)
    compare_path = tmp_path / "compare.json"
    policy_path = tmp_path / "policy.yaml"
    write_json(compare_path, {"k": 10, "summary": {}, "diffs": []})
    policy_path.write_text("fail: []\nwarn: []\n", encoding="utf-8")
    resp = client.post("/gate", json={"compare_path": str(compare_path), "policy_path": str(policy_path)})
    assert resp.status_code == 200
    assert resp.json()["pass"] is True


def test_artifact_list_honors_summary_only_profile(tmp_path: Path) -> None:
    client = _app_with_fakes(tmp_path)
    created = client.post(
        "/runs",
        json={
            "changeset_inline_yaml": "baseline:\\n  solr_url: http://localhost:8983/solr\\n  collection: products\\n"
        },
    )
    job_id = created.json()["job_id"]
    _wait_for_status(client, f"/runs/{job_id}", "succeeded")

    # emulate summary-only profile in generated manifest
    run_dir = tmp_path / "runs" / job_id
    write_json(
        run_dir / "run_manifest.json",
        {"settings": {"security": {"profile": "summary-only"}}},
    )

    artifacts = client.get(f"/artifacts/{job_id}")
    assert artifacts.status_code == 200
    names = {item["name"] for item in artifacts.json()["artifacts"]}
    assert "report.json" in names
    assert "compare.json" not in names

    denied = client.get(f"/artifacts/{job_id}/compare.json")
    assert denied.status_code in {403, 404}
