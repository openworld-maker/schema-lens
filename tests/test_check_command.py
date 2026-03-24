from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from schema_lens.cli import app
from schema_lens.util.io import write_json


runner = CliRunner()


def test_check_compare_input_prints_verdict_and_reasons(tmp_path: Path) -> None:
    compare_path = tmp_path / "compare.json"
    write_json(
        compare_path,
        {
            "k": 10,
            "summary": {
                "avg_overlap_ratio": 0.62,
                "high_risk_percent": 32.0,
                "queries_with_facet_changes_percent": 18.0,
            },
            "performance": {
                "overall": {
                    "baseline_client_latency_ms": {"p95": 100.0},
                    "shadow_client_latency_ms": {"p95": 148.0},
                }
            },
            "diffs": [
                {"numfound_baseline": 10, "numfound_shadow": 0},
                {"numfound_baseline": 11, "numfound_shadow": 0},
                {"numfound_baseline": 11, "numfound_shadow": 1},
                {"numfound_baseline": 10, "numfound_shadow": 2},
            ],
            "root_causes": {
                "summaries": [
                    "PREFIX_MATCHING_REMOVED: Analyzer removed prefix/ngram filter.",
                    "MIN_SHOULD_MATCH_STRICTER: minShouldMatch changed.",
                ]
            },
            "recommendations": {
                "summaries": [
                    "USE_DUAL_FIELD_PREFIX_STRATEGY: Keep prefix matching on dedicated field.",
                    "RELAX_MM_STEPWISE: A stricter mm often cuts recall.",
                ]
            },
        },
    )

    result = runner.invoke(app, ["check", "--compare-input", str(compare_path)])
    assert result.exit_code == 0
    assert "NOT SAFE TO DEPLOY" in result.stdout
    assert "Risk Level: BLOCKER" in result.stdout
    assert "Top Root Causes:" in result.stdout
    assert "Suggested Fix:" in result.stdout


def test_check_fail_on_risk_returns_ci_code(tmp_path: Path) -> None:
    compare_path = tmp_path / "compare.json"
    write_json(
        compare_path,
        {
            "k": 10,
            "summary": {"avg_overlap_ratio": 0.95, "high_risk_percent": 0.0},
            "performance": {
                "overall": {
                    "baseline_client_latency_ms": {"p95": 100.0},
                    "shadow_client_latency_ms": {"p95": 100.0},
                }
            },
            "diffs": [],
        },
    )

    ok = runner.invoke(
        app,
        ["check", "--compare-input", str(compare_path), "--fail-on-risk", "HIGH_RISK"],
    )
    assert ok.exit_code == 0

    strict = runner.invoke(
        app,
        ["check", "--compare-input", str(compare_path), "--fail-on-risk", "SAFE"],
    )
    assert strict.exit_code == 2


def test_check_falls_back_to_demo_when_local_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("schema_lens.cli._can_connect_local_solr", lambda solr_url, verbose: False)
    result = runner.invoke(app, ["check", "--live", "--out", str(tmp_path / "out")])
    assert result.exit_code == 0
    assert "offline demo fallback" in result.stdout.lower()
    assert "Risk Level:" in result.stdout


def test_check_writes_pr_comment_markdown(tmp_path: Path) -> None:
    compare_path = tmp_path / "compare.json"
    out_md = tmp_path / "pr_comment.md"
    write_json(
        compare_path,
        {
            "k": 10,
            "summary": {"avg_overlap_ratio": 0.9, "high_risk_percent": 0.0},
            "performance": {
                "overall": {
                    "baseline_client_latency_ms": {"p95": 100.0},
                    "shadow_client_latency_ms": {"p95": 105.0},
                }
            },
            "diffs": [],
        },
    )
    result = runner.invoke(
        app,
        ["check", "--compare-input", str(compare_path), "--pr-comment-out", str(out_md)],
    )
    assert result.exit_code == 0
    assert out_md.exists()
    text = out_md.read_text(encoding="utf-8")
    assert "## SolrGuard Check Verdict" in text
    assert "**Risk Level:**" in text


def test_queries_ingest_dedupes_by_fingerprint(tmp_path: Path) -> None:
    log_path = tmp_path / "solr.log"
    log_path.write_text(
        "q=bearing+6205&rows=10\nq=bearing+6205&rows=10\nq=industrial+pump&rows=10\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "queries.jsonl"
    state_path = tmp_path / "state.json"
    result = runner.invoke(
        app,
        [
            "queries",
            "ingest",
            "--from",
            str(log_path),
            "--out",
            str(out_path),
            "--state",
            str(state_path),
        ],
    )
    assert result.exit_code == 0
    lines = [line for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2


def test_monitor_live_runs_multiple_iterations(monkeypatch, tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True)
    write_json(
        baseline_dir / "snapshot.json",
        {
            "snapshot_version": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "solr_url": "http://localhost:8983/solr",
            "collection": "products",
            "solr_version": "9.7.0",
            "request_defaults": {},
            "schema_path": "snapshot.schema.json",
            "system_path": "snapshot.system.json",
            "collection_path": "snapshot.collection.json",
            "hash": "sha256:test",
        },
    )
    write_json(baseline_dir / "snapshot.schema.json", {"fields": []})
    write_json(baseline_dir / "snapshot.system.json", {"lucene": {"solr-spec-version": "9.7.0"}})
    write_json(baseline_dir / "snapshot.collection.json", {})
    queries = tmp_path / "queries.jsonl"
    queries.write_text('{"params":{"q":"bearing 6205"}}\n', encoding="utf-8")
    out_dir = tmp_path / "monitor"

    calls = {"count": 0}

    def _fake_run_monitor(**kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        out = kwargs["out_dir"]
        write_json(out / "latest_monitor.json", {"enabled": True, "iteration": calls["count"]})
        return {"latest": {"enabled": True}}

    monkeypatch.setattr("schema_lens.cli.run_monitor", _fake_run_monitor)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    result = runner.invoke(
        app,
        [
            "monitor-live",
            "--baseline-snapshot",
            str(baseline_dir),
            "--queries",
            str(queries),
            "--interval",
            "1s",
            "--iterations",
            "2",
            "--out",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    assert calls["count"] == 2
