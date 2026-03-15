from schema_lens.vector.compare import compare_vector_hybrid


def _result(ids):
    return {
        "docs": [
            {"id": doc_id, "score": 1.0 / (idx + 1), "rank": idx + 1}
            for idx, doc_id in enumerate(ids)
        ],
        "raw_response_meta": {"QTime": 4, "numFound": len(ids)},
        "error": None,
        "skipped": False,
    }


def test_hybrid_contribution_lexical_dominant():
    scenario_replay = {
        "scenario_results": {
            "lexical_only": {
                "scenario": {"name": "lexical_only", "mode": "lexical_only"},
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "baseline": _result(["A", "B", "C", "D"]),
                        "shadow": _result(["A", "B", "C", "D"]),
                    }
                ],
            },
            "vector_only": {
                "scenario": {"name": "vector_only", "mode": "vector_only"},
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "baseline": _result(["E", "F", "G", "H"]),
                        "shadow": _result(["E", "F", "G", "H"]),
                    }
                ],
            },
            "hybrid": {
                "scenario": {"name": "hybrid", "mode": "hybrid"},
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "baseline": _result(["A", "B", "C", "E"]),
                        "shadow": _result(["A", "B", "C", "E"]),
                    }
                ],
            },
        }
    }

    compare = compare_vector_hybrid(scenario_replay=scenario_replay, top_k=4)
    summary = compare["hybrid_contribution"]["hybrid"]["summary"]
    assert (
        summary["avg_contribution_lexical_estimate"]
        > summary["avg_contribution_vector_estimate"]
    )
    assert summary["lexical_dominant_percent"] == 100.0


def test_hybrid_contribution_vector_dominant_confidence_present():
    scenario_replay = {
        "scenario_results": {
            "lexical_only": {
                "scenario": {"name": "lexical_only", "mode": "lexical_only"},
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "baseline": _result(["A", "B", "C", "D", "I", "J"]),
                        "shadow": _result(["A", "B", "C", "D", "I", "J"]),
                    }
                ],
            },
            "vector_only": {
                "scenario": {"name": "vector_only", "mode": "vector_only"},
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "baseline": _result(["V1", "V2", "V3", "V4", "V5", "V6"]),
                        "shadow": _result(["V1", "V2", "V3", "V4", "V5", "V6"]),
                    }
                ],
            },
            "hybrid": {
                "scenario": {"name": "hybrid", "mode": "hybrid"},
                "pairs": [
                    {
                        "query": {"id": 1, "name": "q1"},
                        "baseline": _result(["V1", "V2", "V3", "V4", "A", "B"]),
                        "shadow": _result(["V1", "V2", "V3", "V4", "A", "B"]),
                    }
                ],
            },
        }
    }

    compare = compare_vector_hybrid(scenario_replay=scenario_replay, top_k=6)
    per_query = compare["hybrid_contribution"]["hybrid"]["per_query"][0]
    assert per_query["dominance"] == "vector_dominant"
    assert per_query["confidence"] in {"HIGH", "MEDIUM", "LOW"}
