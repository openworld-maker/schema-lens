from schema_lens.vector.sensitivity import run_hybrid_sensitivity


def test_hybrid_sensitivity_detects_top1_flip():
    scenario_replay = {
        "scenario_results": {
            "hybrid_blend": {
                "scenario": {
                    "name": "hybrid_blend",
                    "mode": "hybrid",
                    "blend": {"method": "linear", "normalize": "none", "rrf_k": 60},
                },
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "shadow": {
                            "blend_inputs": {
                                "lexical_docs": [
                                    {"id": "L1", "score": 1.0},
                                    {"id": "L2", "score": 0.8},
                                ],
                                "vector_docs": [
                                    {"id": "V1", "score": 0.95},
                                    {"id": "V2", "score": 0.8},
                                ],
                            }
                        },
                    }
                ],
            }
        }
    }

    result = run_hybrid_sensitivity(
        scenario_replay=scenario_replay,
        weights=[0.1, 0.5, 0.9],
        top_k=2,
        candidate_pool=10,
    )

    assert result["enabled"] is True
    scenario = result["scenarios"][0]
    assert scenario["queries_with_top1_flip"] >= 1
    assert scenario["query_summaries"][0]["top1_tipping_point"] is not None
