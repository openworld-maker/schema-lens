from schema_lens.rootcause.engine import analyze_root_causes


def test_rootcause_detects_multiple_causes():
    compare_data = {
        "rewrite_diff": {
            "per_query": [
                {
                    "query_id": 1,
                    "risk_flags": ["PARSED_QUERY_SHAPE_CHANGED"],
                }
            ]
        },
        "vector_hybrid": {
            "hybrid_contribution": {
                "hybrid": {"summary": {"vector_dominant_percent": 75.0}}
            }
        },
        "performance": {
            "overall": {
                "baseline_client_latency_ms": {"p95": 10.0},
                "shadow_client_latency_ms": {"p95": 16.0},
            }
        },
        "top_regressions": [
            {
                "query_id": 1,
                "numfound_delta": -3,
                "facet_diffs": {
                    "category": {
                        "new_values": ["safety"],
                        "missing_values": [],
                        "top_deltas": [],
                    }
                },
            }
        ],
    }
    changes = [
        {
            "op": "schema.analyzer.remove_filter",
            "filter_class": "solr.EdgeNGramFilterFactory",
        },
        {"op": "queryparams.set", "set": {"mm": "100%", "qf": "title^1 text"}},
        {"op": "schema.field.update", "field": "title", "set": {"type": "string"}},
    ]
    causes = analyze_root_causes(
        compare_data=compare_data,
        changes=changes,
        baseline_request_defaults={"extra_params": {"mm": "2<75%", "qf": "title^5 text"}},
    )
    codes = {row["cause_code"] for row in causes["overall"]}
    assert "PREFIX_MATCHING_REMOVED" in codes
    assert "ANALYSIS_REMOVED_OR_FIELD_EXACTIFIED" in codes
    assert "VECTOR_DOMINANCE_INCREASED" in codes
    assert "CACHE_OR_LATENCY_REGRESSION" in codes
    assert causes["per_query"][0]["causes"]
