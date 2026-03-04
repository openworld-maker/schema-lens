from schema_lens.compare.rewrite_diff import (
    extract_rewrite_info,
    load_synonym_rules_from_changes,
    run_rewrite_diff,
)


def test_extract_rewrite_info_handles_variant_debug_shapes():
    payload = {
        "debug": {
            "parsedQuery": "+title:ss",
            "parsedQuery_toString": "title:ss",
        }
    }
    out = extract_rewrite_info(payload)
    assert out["parsedquery"] == "+title:ss"
    assert out["parsedquery_toString"] == "title:ss"


def test_load_synonym_rules_from_changes(tmp_path):
    source = tmp_path / "synonyms_v2.txt"
    source.write_text("ss=>stainless steel\nrfq,request for quote\n", encoding="utf-8")
    changes = [
        {
            "op": "schema.synonym.update",
            "mode": "replace",
            "source_file": str(source),
            "target": {"files": [{"path": "conf/synonyms.txt"}]},
        }
    ]

    rules = load_synonym_rules_from_changes(changes, changeset_path=str(tmp_path / "c.yaml"))
    assert any(rule["source"] == "ss" for rule in rules)
    assert any(rule["source"] == "rfq" for rule in rules)


def test_run_rewrite_diff_computes_clause_and_synonym_flags(monkeypatch):
    captured_params = []

    def fake_select(_client, collection, params):
        captured_params.append(dict(params))
        if collection == "baseline":
            return {
                "debug": {
                    "parsedquery": "+title:ss +text:washer",
                    "parsedquery_toString": "title:ss text:washer",
                }
            }
        return {
            "debug": {
                "parsedquery": "+title:stainless +title:steel +text:washer",
                "parsedquery_toString": "title:stainless title:steel text:washer",
            }
        }

    monkeypatch.setattr("schema_lens.compare.rewrite_diff.select", fake_select)

    replay_pairs = [
        {
            "query": {
                "id": 1,
                "raw_line": "ss washer",
                "params": {"q": "ss washer", "defType": "edismax"},
            },
            "effective_params": {"q": "ss washer", "defType": "edismax", "mm": "2<75%"},
        }
    ]
    diffs = [
        {
            "query_id": 1,
            "risk_severity": "HIGH",
            "topk_overlap_count": 1,
            "kendall_tau": 0.0,
        }
    ]

    out = run_rewrite_diff(
        baseline_client=object(),
        baseline_collection="baseline",
        shadow_client=object(),
        shadow_collection="shadow",
        replay_pairs=replay_pairs,
        diffs=diffs,
        k=10,
        rewrite_cfg={
            "enabled": True,
            "max_queries": 10,
            "debug_mode": "results",
            "clause_spike_threshold": 1,
            "always_for_high_risk": True,
        },
        synonym_rules=[{"source": "ss", "targets": ["stainless steel"]}],
        has_synonym_changes=True,
    )

    assert out["queries_analyzed"] == 1
    row = out["per_query"][0]
    assert row["clause_delta"] >= 1
    assert "PARSED_QUERY_SHAPE_CHANGED" in row["risk_flags"]
    assert "REWRITE_CLAUSE_SPIKE" in row["risk_flags"]
    assert "SYNONYM_EXPANSION_CHANGED" in row["risk_flags"]
    assert row["mm_impact"] == "clause_count_changed_under_mm"
    assert any(params.get("debug") in {"results", "query,results"} for params in captured_params)


def test_run_rewrite_diff_falls_back_when_results_has_no_parsed_query(monkeypatch):
    captured_params = []

    def fake_select(_client, _collection, params):
        captured_params.append(dict(params))
        if params.get("debug"):
            return {"debug": {"explain": {}}}
        return {"debug": {"parsedquery": "+title:ss", "parsedquery_toString": "title:ss"}}

    monkeypatch.setattr("schema_lens.compare.rewrite_diff.select", fake_select)

    out = run_rewrite_diff(
        baseline_client=object(),
        baseline_collection="baseline",
        shadow_client=object(),
        shadow_collection="shadow",
        replay_pairs=[
            {
                "query": {"id": 1, "raw_line": "ss", "params": {"q": "ss"}},
                "effective_params": {"q": "ss"},
            }
        ],
        diffs=[
            {
                "query_id": 1,
                "risk_severity": "HIGH",
                "topk_overlap_count": 1,
                "kendall_tau": 1.0,
            }
        ],
        k=10,
        rewrite_cfg={"enabled": True, "max_queries": 10, "debug_mode": "results"},
        synonym_rules=[],
        has_synonym_changes=False,
    )

    assert out["per_query"][0]["baseline"]["parsedquery_toString"] == "title:ss"
    assert any(params.get("debug") == "query,results" for params in captured_params)
    assert any(params.get("debugQuery") == "true" for params in captured_params)
