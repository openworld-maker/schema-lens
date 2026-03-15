from pathlib import Path

import pytest
from typer.testing import CliRunner

from schema_lens.cli import app
from schema_lens.monitor.drift import compute_drift_summary
from schema_lens.monitor.runner import run_monitor
from schema_lens.snapshot.snapshotter import snapshot_hash
from schema_lens.util.io import write_json


def test_compute_drift_summary():
    summary = compute_drift_summary(
        {"summary": {"avg_overlap": 0.9, "high_risk_percent": 2.0}},
        {"summary": {"avg_overlap": 0.7, "high_risk_percent": 5.0}},
    )
    assert summary["avg_overlap"]["delta"] == pytest.approx(-0.2)
    assert summary["high_risk_percent"]["delta"] == 3.0


def test_run_monitor_appends_history(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    schema = {"schema": {"fields": [{"name": "id"}]}}
    system = {"lucene": {"solr-spec-version": "9.0.0"}}
    collection_state = {}
    computed_hash = snapshot_hash(
        solr_url="http://localhost:8983/solr",
        collection="products",
        schema=schema,
        system=system,
        collection_state=collection_state,
        request_defaults={},
    )
    write_json(
        snapshot_dir / "snapshot.json",
        {
            "snapshot_version": 1,
            "solr_url": "http://localhost:8983/solr",
            "collection": "products",
            "schema_path": "snapshot.schema.json",
            "system_path": "snapshot.system.json",
            "collection_path": "snapshot.collection.json",
            "request_defaults": {},
            "hash": computed_hash,
        },
    )
    write_json(snapshot_dir / "snapshot.schema.json", schema)
    write_json(snapshot_dir / "snapshot.system.json", system)
    write_json(snapshot_dir / "snapshot.collection.json", collection_state)
    write_json(snapshot_dir / "report.json", {"summary": {"avg_overlap": 0.8}})
    write_json(
        snapshot_dir / "replay.json",
        {
            "k": 10,
            "pairs": [
                {
                    "query": {"id": 1, "params": {"q": "bolt"}},
                    "baseline": {"docs": [{"id": "A", "rank": 1}]},
                }
            ],
        },
    )
    queries_path = tmp_path / "queries.jsonl"
    queries_path.write_text('{"params":{"q":"bolt"}}\n', encoding="utf-8")

    out_dir = tmp_path / "monitor"
    out_dir.mkdir()
    first = run_monitor(
        baseline_snapshot_dir=snapshot_dir,
        queries_path=queries_path,
        query_format="jsonl",
        interval="24h",
        out_dir=out_dir,
    )
    second = run_monitor(
        baseline_snapshot_dir=snapshot_dir,
        queries_path=queries_path,
        query_format="jsonl",
        interval="24h",
        out_dir=out_dir,
    )
    assert first["latest"]["enabled"] is True
    assert len(second["history"]) == 2
    assert (out_dir / "latest_monitor.json").exists()
    assert (out_dir / "monitor_history.jsonl").exists()


def test_monitor_cli_emits_latest_monitor_path(tmp_path: Path):
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    schema = {"schema": {"fields": [{"name": "id"}]}}
    system = {"lucene": {"solr-spec-version": "9.0.0"}}
    collection_state = {}
    computed_hash = snapshot_hash(
        solr_url="http://localhost:8983/solr",
        collection="products",
        schema=schema,
        system=system,
        collection_state=collection_state,
        request_defaults={},
    )
    write_json(
        snapshot_dir / "snapshot.json",
        {
            "snapshot_version": 1,
            "solr_url": "http://localhost:8983/solr",
            "collection": "products",
            "schema_path": "snapshot.schema.json",
            "system_path": "snapshot.system.json",
            "collection_path": "snapshot.collection.json",
            "request_defaults": {},
            "hash": computed_hash,
        },
    )
    write_json(snapshot_dir / "snapshot.schema.json", schema)
    write_json(snapshot_dir / "snapshot.system.json", system)
    write_json(snapshot_dir / "snapshot.collection.json", collection_state)
    write_json(snapshot_dir / "report.json", {"summary": {"avg_overlap": 0.8}})
    queries_path = tmp_path / "queries.jsonl"
    queries_path.write_text('{"params":{"q":"bolt"}}\n', encoding="utf-8")
    out_dir = tmp_path / "monitor"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "monitor",
            "--baseline-snapshot",
            str(snapshot_dir),
            "--queries",
            str(queries_path),
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert str((out_dir / "latest_monitor.json").resolve()) in result.stdout
    assert (out_dir / "latest_monitor.json").exists()
    assert not (out_dir / "monitor.json").exists()
