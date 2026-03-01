from pathlib import Path

from schema_lens.queries.loader import load_queries
from schema_lens.replay.runner import run_replay


def test_replay_captures_facets(monkeypatch, tmp_path: Path):
    qpath = tmp_path / "queries.txt"
    qpath.write_text("q=bearing\n", encoding="utf-8")
    queries = load_queries(qpath)
    seen_params = {}

    def fake_select(_client, _collection, params):
        seen_params.update(params)
        return {
            "responseHeader": {"QTime": 1, "status": 0},
            "response": {"numFound": 2, "docs": [{"id": "1", "score": 1.0}]},
            "facet_counts": {
                "facet_fields": {
                    "category": ["tools", 5, "hardware", 3],
                }
            },
        }

    monkeypatch.setattr("schema_lens.replay.runner.select", fake_select)
    replay = run_replay(
        baseline_client=object(),
        baseline_collection="products",
        shadow_client=object(),
        shadow_collection="products_shadow",
        queries=queries,
        request_defaults={},
        k=10,
        capture_cfg={
            "facets": {"enabled": True, "fields": ["category"], "limit": 20},
            "track_numfound": True,
            "track_sort": True,
        },
    )
    assert seen_params["facet"] == "true"
    assert seen_params["facet.field"] == ["category"]
    pair = replay["pairs"][0]
    assert pair["baseline"]["facet_counts"]["category"]["tools"] == 5

