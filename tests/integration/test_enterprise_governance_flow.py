from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from schema_lens.cli import app
from schema_lens.util.io import read_json, write_json


def test_enterprise_governance_cli_flow(tmp_path: Path) -> None:
    runner = CliRunner()
    compare = tmp_path / "compare.json"
    summary_md = tmp_path / "summary.md"

    write_json(
        compare,
        {
            "k": 10,
            "summary": {"avg_overlap": 0.92, "high_risk_percent": 1.0},
            "diffs": [
                {
                    "query_id": 1,
                    "risk_severity": "LOW",
                    "overlap_ratio": 0.9,
                    "params": {"q": "safety gloves"},
                    "shadow_topk_ids": ["A", "B"],
                }
            ],
            "performance": {
                "overall": {
                    "baseline_client_latency_ms": {"p95": 80},
                    "shadow_client_latency_ms": {"p95": 82},
                    "baseline_qtime_ms": {"p95": 40},
                    "shadow_qtime_ms": {"p95": 41},
                },
                "caches": {"filterCache": {"evictions": {"delta_pct": 1.0}}},
                "index": {"delta": {"indexSizeBytes": {"delta_pct": 2.0}}},
            },
        },
    )

    gate = runner.invoke(
        app,
        [
            "gate",
            "--compare",
            str(compare),
            "--policy",
            "examples/policy/perf_gate_default.yaml",
        ],
    )
    assert gate.exit_code == 0
    assert '"pass": true' in gate.stdout

    summarize = runner.invoke(
        app,
        [
            "ci",
            "summarize",
            "--compare",
            str(compare),
            "--policy",
            "examples/policy/perf_gate_default.yaml",
            "--out",
            str(summary_md),
        ],
    )
    assert summarize.exit_code == 0
    payload = summary_md.read_text(encoding="utf-8")
    assert "SolrGuard CI Summary" in payload
    assert "Gate" in payload

    parsed = read_json(compare)
    assert parsed["summary"]["avg_overlap"] == 0.92
