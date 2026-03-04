from schema_lens.report.json_report import build_report_json


def test_build_report_json_handles_empty_dropped_docs():
    report = build_report_json(
        manifest={"run_id": "r1"},
        replay_data={"stats": {"failures": 1}},
        compare_data={
            "summary": {"queries_total": 2, "avg_overlap": 0.5, "high_risk_percent": 50.0},
            "rewrite_diff": {"enabled": True, "queries_analyzed": 1, "per_query": []},
            "top_regressions": [
                {
                    "query_id": 1,
                    "raw_line": "q=foo",
                    "risk_severity": "HIGH",
                    "topk_overlap_count": 1,
                    "jaccard": 0.2,
                    "kendall_tau": None,
                    "dropped_docs": [],
                }
            ],
            "diffs": [],
            "explain_bundles": [],
        },
    )

    assert report["summary"]["failures"] == 1
    assert report["top_regressions"][0]["dropped_top_doc"] is None
    assert report["query_rewrite_impact"]["enabled"] is True


def test_build_report_json_summary_defaults():
    report = build_report_json(
        manifest={},
        replay_data={},
        compare_data={},
    )
    assert report["summary"] == {
        "queries_total": 0,
        "failures": 0,
        "avg_overlap": 0,
        "high_risk_percent": 0,
        "avg_numfound_delta": 0,
        "avg_sort_instability_ratio": 0,
        "queries_with_facet_changes_percent": 0,
    }
