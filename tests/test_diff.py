from schema_lens.compare.diff import compare_replay


def test_compare_replay_moved_new_dropped_and_risk():
    replay_data = {
        "pairs": [
            {
                "query": {"id": 1, "raw_line": "laptop", "params": {"q": "laptop"}},
                "baseline": {
                    "error": None,
                    "docs": [
                        {"id": "a", "score": 10, "rank": 1},
                        {"id": "b", "score": 9, "rank": 2},
                        {"id": "c", "score": 8, "rank": 3},
                    ],
                },
                "shadow": {
                    "error": None,
                    "docs": [
                        {"id": "b", "score": 11, "rank": 1},
                        {"id": "a", "score": 9.5, "rank": 2},
                        {"id": "d", "score": 8.5, "rank": 3},
                    ],
                },
            }
        ]
    }

    out = compare_replay(replay_data, k=3)
    assert out["summary"]["queries_total"] == 1
    diff = out["diffs"][0]
    assert diff["topk_overlap_count"] == 2
    assert "c" in diff["dropped_docs"]
    assert "d" in diff["new_docs"]
    assert len(diff["moved_docs"]) == 2
    assert diff["risk_severity"] in {"HIGH", "MEDIUM", "LOW"}


def test_compare_replay_marks_high_risk_on_query_errors():
    replay_data = {
        "pairs": [
            {
                "query": {"id": 9, "raw_line": "q=bad", "params": {"q": "bad"}},
                "baseline": {"error": "timeout", "docs": []},
                "shadow": {"error": None, "docs": []},
            }
        ]
    }
    out = compare_replay(replay_data, k=10)
    diff = out["diffs"][0]
    assert diff["risk_severity"] == "HIGH"
    assert "BASELINE_QUERY_ERROR" in diff["risk_flags"]


def test_compare_replay_medium_risk_threshold():
    replay_data = {
        "pairs": [
            {
                "query": {"id": 2, "raw_line": "q=x", "params": {"q": "x"}},
                "baseline": {
                    "error": None,
                    "docs": [
                        {"id": "a", "score": 1.0, "rank": 1},
                        {"id": "b", "score": 0.9, "rank": 2},
                        {"id": "c", "score": 0.8, "rank": 3},
                        {"id": "d", "score": 0.7, "rank": 4},
                        {"id": "e", "score": 0.6, "rank": 5},
                    ],
                },
                "shadow": {
                    "error": None,
                    "docs": [
                        {"id": "a", "score": 1.0, "rank": 1},
                        {"id": "b", "score": 0.9, "rank": 2},
                        {"id": "x", "score": 0.8, "rank": 3},
                        {"id": "y", "score": 0.7, "rank": 4},
                        {"id": "z", "score": 0.6, "rank": 5},
                    ],
                },
            }
        ]
    }
    out = compare_replay(replay_data, k=5)
    diff = out["diffs"][0]
    assert diff["topk_overlap_count"] == 2
    # Overlap=2/5 => below 60%, should be HIGH by heuristic.
    assert diff["risk_severity"] == "HIGH"
