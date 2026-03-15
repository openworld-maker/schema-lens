from pathlib import Path

from schema_lens.compare.gate import evaluate_gate
from schema_lens.perf.analyzer import analyze_performance
from schema_lens.perf.grouping import classify_query
from schema_lens.perf.percentiles import percentile, summarize_percentiles


def test_percentile_and_summary():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 40.0
    summary = summarize_percentiles(values, [50, 95])
    assert summary["p50"] == 25.0
    assert summary["p95"] > summary["p50"]


def test_classify_query_groups():
    labels = classify_query(
        params={"fq": ["category:tools"], "sort": "price asc"},
        request_mode="json_request",
        scenario_mode="hybrid",
        facet_counts={"category": {"tools": 10}},
    )
    assert "hybrid" in labels
    assert "filter_heavy" in labels
    assert "facet_heavy" in labels
    assert "sort_heavy" in labels


def test_analyze_performance_and_gate_metrics():
    replay_data = {
        "pairs": [
            {
                "query": {"id": 1, "params": {"q": "bolt", "fq": ["category:fasteners"]}},
                "baseline": {"raw_response_meta": {"client_latency_ms": 10, "QTime": 8}},
                "shadow": {"raw_response_meta": {"client_latency_ms": 18, "QTime": 14}},
            },
            {
                "query": {"id": 2, "params": {"q": "nitrile gloves", "sort": "score desc"}},
                "baseline": {
                    "raw_response_meta": {"client_latency_ms": 12, "QTime": 9},
                    "facet_counts": {"category": {"safety": 4}},
                },
                "shadow": {
                    "raw_response_meta": {"client_latency_ms": 25, "QTime": 20},
                    "facet_counts": {"category": {"safety": 4}},
                },
            },
        ]
    }
    compare_data = {"summary": {}, "diffs": []}
    baseline_snapshot = {
        "caches": {"filterCache": {"hits": 100, "inserts": 50, "evictions": 10, "hitratio": 0.9}},
        "index": {"indexSizeBytes": 1000, "numDocs": 10, "deletedDocs": 0, "segmentCount": 1},
    }
    shadow_snapshot = {
        "caches": {"filterCache": {"hits": 110, "inserts": 60, "evictions": 20, "hitratio": 0.85}},
        "index": {"indexSizeBytes": 1250, "numDocs": 10, "deletedDocs": 0, "segmentCount": 2},
    }
    perf = analyze_performance(
        replay_data=replay_data,
        compare_data=compare_data,
        baseline_snapshot=baseline_snapshot,
        shadow_snapshot=shadow_snapshot,
        changes=[{"op": "schema.field.update", "field": "title", "set": {"stored": True}}],
        percentiles=[50, 95],
    )
    assert perf["enabled"] is True
    assert (
        perf["overall"]["shadow_client_latency_ms"]["p95"]
        > perf["overall"]["baseline_client_latency_ms"]["p95"]
    )
    assert perf["caches"]["filterCache"]["evictions"]["delta"] == 10.0
    assert perf["index"]["delta"]["indexSizeBytes"]["delta"] == 250
    assert perf["index"]["schema_heuristics"][0]["kind"] == "stored"
    assert perf["callouts"]

    gate_result = evaluate_gate(
        compare_data={"summary": {}, "diffs": [], "performance": perf},
        policy_data={
            "fail": [{"metric": "p95_latency_regression_pct", "op": ">", "value": 20}],
            "warn": [],
        },
        policy_dir=Path("."),
    )
    assert gate_result["pass"] is False
