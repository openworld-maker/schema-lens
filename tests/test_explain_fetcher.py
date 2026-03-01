from __future__ import annotations

from typing import Any

from schema_lens.compare.explain_fetcher import _pick_doc_ids, fetch_explains


def test_pick_doc_ids_prioritizes_and_deduplicates():
    diff = {
        "dropped_docs": ["d1", "d2"],
        "moved_docs": [{"id": "d2", "delta": 3}, {"id": "d3", "delta": -5}],
        "new_docs": ["d4"],
    }
    assert _pick_doc_ids(diff, max_docs=3) == ["d1", "d2", "d3"]


def test_fetch_explains_filters_low_risk_and_handles_failures(monkeypatch):
    def fake_select(_client: Any, collection: str, params: dict[str, Any]):
        if collection == "shadow" and params.get("q") == "q2":
            raise RuntimeError("shadow explain failed")
        return {
            "debug": {
                "explain": {
                    "doc1": f"explain-{collection}-doc1",
                    "doc2": f"explain-{collection}-doc2",
                }
            }
        }

    monkeypatch.setattr("schema_lens.compare.explain_fetcher.select", fake_select)

    replay_pairs = [
        {"query": {"id": 1, "params": {"q": "q1"}}},
        {"query": {"id": 2, "params": {"q": "q2"}}},
    ]
    diffs = [
        {
            "query_id": 1,
            "risk_severity": "LOW",
            "topk_overlap_count": 10,
            "kendall_tau": 1.0,
            "dropped_docs": ["doc1"],
            "moved_docs": [],
            "new_docs": [],
        },
        {
            "query_id": 2,
            "risk_severity": "HIGH",
            "topk_overlap_count": 1,
            "kendall_tau": 0.1,
            "dropped_docs": ["doc1"],
            "moved_docs": [{"id": "doc2", "delta": 4}],
            "new_docs": [],
        },
    ]

    bundles = fetch_explains(
        baseline_client=object(),
        baseline_collection="baseline",
        shadow_client=object(),
        shadow_collection="shadow",
        replay_pairs=replay_pairs,
        diffs=diffs,
        k=10,
        max_queries=5,
        max_docs_per_query=2,
    )

    assert len(bundles) == 2
    assert all(bundle["query_id"] == 2 for bundle in bundles)
    assert bundles[0]["baseline_explain_raw"] == "explain-baseline-doc1"
    # shadow fails for q2 and should be recorded as None, not crash.
    assert bundles[0]["shadow_explain_raw"] is None
