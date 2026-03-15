from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.runtime.snapshot_compat_service import run_snapshot_and_compat


def test_run_snapshot_and_compat_with_loaded_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "out"
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "schema_lens.runtime.snapshot_compat_service.load_snapshot",
        lambda _p: {
            "manifest": {"id": "m1", "hash": "h1"},
            "schema": {"fields": []},
            "system": {"lucene": {"solr-spec-version": "9.8.0"}},
            "collection_state": {"collections": {}},
            "hash": "h1",
        },
    )

    runtime = run_snapshot_and_compat(
        snapshot_path=snapshot_dir,
        baseline_url="http://localhost:8983/solr",
        baseline_collection="products",
        out_dir=out,
        request_defaults={},
        verbose=False,
        outputs={
            "snapshot_json": str(out / "snapshot.json"),
            "snapshot_schema_json": str(out / "snapshot.schema.json"),
            "snapshot_system_json": str(out / "snapshot.system.json"),
            "snapshot_collection_json": str(out / "snapshot.collection.json"),
            "snapshot_hash_txt": str(out / "snapshot.hash.txt"),
            "inspect_json": str(out / "inspect.json"),
        },
        manifest_inputs={},
    )

    assert runtime.compat_payload["solr_version"].startswith("9")
    assert (out / "inspect.json").exists()
