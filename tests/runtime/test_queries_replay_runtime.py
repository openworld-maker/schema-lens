from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.runtime.data_query_service import load_or_extract_queries
from schema_lens.runtime.replay_compare_service import run_replay_stage


def test_load_or_extract_queries_without_persist(tmp_path: Path) -> None:
    log_file = tmp_path / "queries.jsonl"
    log_file.write_text('{"params":{"q":"laptop","rows":"10"}}\n', encoding="utf-8")

    query_cases = load_or_extract_queries(
        query_source_type="log",
        queries_source={"format": "solr_params"},
        queries_path=log_file,
        query_cfg={"max_queries": 10, "sanitize": {"enabled": True}},
        outputs={"queries_extracted_jsonl": str(tmp_path / "queries_extracted.jsonl")},
        manifest_inputs={},
        manifest_settings={},
        persist_sensitive_effective=False,
    )

    assert len(query_cases) == 1
    assert query_cases[0].params.get("q") == "laptop"


def test_run_replay_stage_merges_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_merge(defaults, _changes):
        return {**defaults, "rows": "5"}

    def _fake_run_replay(**kwargs):
        captured["request_defaults"] = kwargs["request_defaults"]
        return {"pairs": [], "stats": {"failures": 0}}

    monkeypatch.setattr("schema_lens.runtime.replay_compare_service.merge_queryparams", _fake_merge)
    monkeypatch.setattr("schema_lens.runtime.replay_compare_service.run_replay", _fake_run_replay)

    replay_data, capture_cfg = run_replay_stage(
        baseline_client=object(),
        baseline_collection="products",
        shadow_client=object(),
        shadow_collection="products_shadow",
        query_cases=[],
        request_defaults={"q.op": "AND"},
        changes=[],
        replay_cfg={"capture": {"enabled": True}},
        k=10,
        baseline_url="http://baseline",
        shadow_url="http://shadow",
    )

    assert captured["request_defaults"] == {"q.op": "AND", "rows": "5"}
    assert capture_cfg == {"enabled": True}
    assert replay_data["baseline"]["collection"] == "products"
