from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient

from schema_lens.api.app import create_api_app
from schema_lens.api.jobs import JobManager
from schema_lens.api.models import RunCreateRequest
from schema_lens.api.security import ApiIdentity, HeaderTokenAuthProvider, RoleBasedRbacPolicy
from schema_lens.api.storage import ApiStorage
from schema_lens.util.io import write_json


def _fake_run_executor(changeset_path: Path, request: RunCreateRequest, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "report.json", {"summary": {"queries_total": 1}})


def _wait_for_status(client: TestClient, job_id: str, wanted: str, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        resp = client.get(f"/runs/{job_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last.get("status") == wanted:
            return last
        time.sleep(0.05)
    return last


def test_auth_rbac_and_audit(tmp_path: Path) -> None:
    storage = ApiStorage(tmp_path)
    manager = JobManager(storage, executor=_fake_run_executor)
    provider = HeaderTokenAuthProvider(
        token_map={
            "viewer-token": ApiIdentity(principal="viewer", roles=("viewer",), authenticated=True),
            "operator-token": ApiIdentity(principal="operator", roles=("operator",), authenticated=True),
        }
    )
    policy = RoleBasedRbacPolicy({"POST /runs": ["operator"]})
    app = create_api_app(
        base_dir=tmp_path,
        job_manager=manager,
        auth_provider=provider,
        rbac_policy=policy,
    )
    client = TestClient(app)

    missing = client.get("/health")
    assert missing.status_code == 401

    viewer_health = client.get("/health", headers={"x-solrguard-token": "viewer-token"})
    assert viewer_health.status_code == 200

    viewer_run = client.post(
        "/runs",
        headers={"x-solrguard-token": "viewer-token"},
        json={"changeset_inline_yaml": "baseline:\n  solr_url: http://localhost:8983/solr\n  collection: products\n"},
    )
    assert viewer_run.status_code == 403

    operator_run = client.post(
        "/runs",
        headers={"x-solrguard-token": "operator-token"},
        json={"changeset_inline_yaml": "baseline:\n  solr_url: http://localhost:8983/solr\n  collection: products\n"},
    )
    assert operator_run.status_code == 200

    legacy_header = client.get("/health", headers={"x-schema-lens-token": "viewer-token"})
    assert legacy_header.status_code == 200

    audit_log = tmp_path / "logs" / "api_audit.jsonl"
    assert audit_log.exists()
    lines = [json.loads(line) for line in audit_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("outcome") == "auth_failed" for row in lines)
    assert any(row.get("outcome") == "rbac_denied" for row in lines)
    assert any(row.get("outcome") == "ok" and row.get("principal") == "operator" for row in lines)


def test_external_worker_pull_mode(tmp_path: Path) -> None:
    storage = ApiStorage(tmp_path)
    manager = JobManager(storage, executor=_fake_run_executor, worker_mode="external")
    app = create_api_app(base_dir=tmp_path, job_manager=manager)
    client = TestClient(app)

    created = client.post(
        "/runs",
        json={"changeset_inline_yaml": "baseline:\n  solr_url: http://localhost:8983/solr\n  collection: products\n"},
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    queued = client.get(f"/runs/{job_id}")
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"

    assert manager.run_pending(limit=1) == 1
    done = _wait_for_status(client, job_id, "succeeded")
    assert done["status"] == "succeeded"
