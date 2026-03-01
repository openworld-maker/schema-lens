from schema_lens.compare.diff import compare_replay
from schema_lens.compare.numfound import numfound_delta
from schema_lens.compare.sort import sort_instability_ratio


def test_numfound_delta():
    b, s, d = numfound_delta({"numFound": 10}, {"numFound": 7})
    assert b == 10
    assert s == 7
    assert d == -3


def test_sort_instability_ratio():
    ratio = sort_instability_ratio(["a", "b", "c"], ["b", "a", "c"])
    assert ratio == 2 / 3


def test_compare_replay_includes_numfound_and_sort():
    replay_data = {
        "pairs": [
            {
                "query": {"id": 1, "raw_line": "q=x", "params": {"q": "x"}},
                "baseline": {
                    "error": None,
                    "raw_response_meta": {"numFound": 10},
                    "docs": [{"id": "a", "score": 2.0}, {"id": "b", "score": 1.0}],
                    "facet_counts": {"category": {"tools": 2}},
                },
                "shadow": {
                    "error": None,
                    "raw_response_meta": {"numFound": 8},
                    "docs": [{"id": "b", "score": 2.0}, {"id": "a", "score": 1.0}],
                    "facet_counts": {"category": {"tools": 1, "new": 1}},
                },
            }
        ]
    }
    out = compare_replay(replay_data, k=2)
    diff = out["diffs"][0]
    assert diff["numfound_delta"] == -2
    assert diff["sort_instability_ratio"] > 0
    assert "category" in diff["facet_diffs"]
    assert "avg_numfound_delta" in out["summary"]

