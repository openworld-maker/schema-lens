from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.queries.loader import load_queries
from schema_lens.replay.runner import run_replay


def _query_cases(tmp_path: Path):
    path = tmp_path / "queries.txt"
    path.write_text("laptop\nq=charger\n", encoding="utf-8")
    return load_queries(path)


def test_run_replay_success_and_param_merging(monkeypatch, tmp_path: Path):
    calls = []

    def fake_select(_client, collection, params):
        calls.append((collection, dict(params)))
        return {
            "responseHeader": {"QTime": 5, "status": 0},
            "response": {"numFound": 2, "docs": [{"id": "1", "score": 2.0}]},
        }

    monkeypatch.setattr("schema_lens.replay.runner.select", fake_select)

    replay = run_replay(
        baseline_client=object(),
        baseline_collection="baseline",
        shadow_client=object(),
        shadow_collection="shadow",
        queries=_query_cases(tmp_path),
        request_defaults={"fl": "title", "extra_params": {"defType": "edismax"}},
        k=10,
    )

    assert replay["stats"]["queries_total"] == 2
    assert replay["stats"]["failures"] == 0
    assert len(replay["pairs"]) == 2
    assert replay["pairs"][0]["effective_params"]["defType"] == "edismax"

    first_call = calls[0][1]
    assert first_call["rows"] == "10"
    assert first_call["fl"] == "title,id,score"
    assert first_call["defType"] == "edismax"


def test_run_replay_records_partial_failures(monkeypatch, tmp_path: Path):
    counter = {"n": 0}

    def flaky_select(_client, collection, _params):
        counter["n"] += 1
        if collection == "shadow" and counter["n"] == 2:
            raise RuntimeError("shadow failed once")
        return {
            "responseHeader": {"QTime": 1, "status": 0},
            "response": {"numFound": 1, "docs": [{"id": "1", "score": 1.0}]},
        }

    monkeypatch.setattr("schema_lens.replay.runner.select", flaky_select)

    replay = run_replay(
        baseline_client=object(),
        baseline_collection="baseline",
        shadow_client=object(),
        shadow_collection="shadow",
        queries=_query_cases(tmp_path),
        request_defaults={},
        k=5,
    )

    assert replay["stats"]["failures"] == 1
    assert replay["pairs"][0]["shadow"]["error"] == "shadow failed once"
    assert replay["pairs"][1]["shadow"]["error"] is None


@pytest.mark.parametrize(
    ("fl", "expected"),
    [
        ("id", "id,score"),
        ("score", "score,id"),
        ("title", "title,id,score"),
    ],
)
def test_run_replay_enforces_id_score_in_fl(monkeypatch, tmp_path: Path, fl: str, expected: str):
    captured = {}

    def fake_select(_client, _collection, params):
        captured["fl"] = params["fl"]
        return {
            "responseHeader": {"QTime": 1, "status": 0},
            "response": {"numFound": 0, "docs": []},
        }

    monkeypatch.setattr("schema_lens.replay.runner.select", fake_select)
    cases = _query_cases(tmp_path)

    run_replay(
        baseline_client=object(),
        baseline_collection="baseline",
        shadow_client=object(),
        shadow_collection="shadow",
        queries=[cases[0]],
        request_defaults={"fl": fl},
        k=3,
    )

    assert captured["fl"] == expected
