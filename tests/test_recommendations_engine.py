from schema_lens.recommend.engine import build_recommendations


def test_recommendations_map_from_root_causes():
    root_causes = {
        "overall": [
            {"cause_code": "PREFIX_MATCHING_REMOVED"},
            {"cause_code": "VECTOR_DOMINANCE_INCREASED"},
            {"cause_code": "CACHE_OR_LATENCY_REGRESSION"},
        ]
    }
    recommendations = build_recommendations(root_causes)
    codes = {row["recommendation_code"] for row in recommendations["overall"]}
    assert "USE_DUAL_FIELD_PREFIX_STRATEGY" in codes
    assert "RUN_HYBRID_WEIGHT_SWEEP" in codes
    assert "REDUCE_CACHE_PRESSURE_OR_DOCVALUES_HOTPATH" in codes
    assert recommendations["summaries"]
