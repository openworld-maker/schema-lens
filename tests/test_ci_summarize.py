from pathlib import Path

from schema_lens.ci.summarize import build_ci_summary_markdown


def test_ci_summary_contains_required_sections(tmp_path: Path):
    compare = {
        "summary": {
            "queries_total": 2,
            "avg_overlap": 0.8,
            "high_risk_percent": 10.0,
            "avg_numfound_delta": -1.5,
            "avg_sort_instability_ratio": 0.2,
        },
        "top_regressions": [
            {
                "query_id": 1,
                "risk_severity": "HIGH",
                "topk_overlap_count": 1,
                "kendall_tau": 0.1,
            }
        ],
    }
    md = build_ci_summary_markdown(compare, compare_path=tmp_path / "compare.json")
    assert "# Schema-Lens CI Summary" in md
    assert "## Overall Metrics" in md
    assert "## Gate Verdict" in md
    assert "## Top Regressions (10)" in md
    assert "## Artifact Paths" in md
