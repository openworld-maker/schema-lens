from schema_lens.report.json_report import build_report_json


def test_report_includes_vector_hybrid_sections():
    report = build_report_json(
        manifest={"run_id": "r1"},
        replay_data={"stats": {"failures": 0}},
        compare_data={
            "summary": {"queries_total": 1, "avg_overlap": 1.0, "high_risk_percent": 0.0},
            "vector_hybrid": {
                "enabled": True,
                "scenario_summaries": [{"scenario_name": "hybrid", "mode": "hybrid"}],
                "narratives": ["Vector similarity now dominates."],
            },
            "hybrid_sensitivity": {"enabled": True, "scenarios": []},
            "top_regressions": [],
            "diffs": [],
            "rewrite_diff": {"enabled": False},
            "explain_bundles": [],
        },
    )

    assert report["vector_hybrid_simulation"]["enabled"] is True
    assert report["hybrid_sensitivity"]["enabled"] is True
