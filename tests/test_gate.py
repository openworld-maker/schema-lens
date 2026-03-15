from pathlib import Path

from schema_lens.compare.gate import evaluate_gate, load_gate_policy


def _compare_payload():
    return {
        "k": 10,
        "summary": {"avg_overlap_ratio": 0.85, "high_risk_percent": 2.0, "med_risk_percent": 10.0},
        "diffs": [
            {
                "params": {"q": "a"},
                "risk_severity": "LOW",
                "overlap_ratio": 0.9,
                "shadow_topk_ids": ["A1", "A2"],
            },
            {
                "params": {"q": "b"},
                "risk_severity": "HIGH",
                "overlap_ratio": 0.4,
                "shadow_topk_ids": ["B1"],
            },
        ],
    }


def test_gate_pass(tmp_path: Path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: 1
fail:
  - metric: avg_overlap
    op: "<"
    value: 0.8
""",
        encoding="utf-8",
    )
    policy = load_gate_policy(policy_path)
    result = evaluate_gate(compare_data=_compare_payload(), policy_data=policy, policy_dir=tmp_path)
    assert result["pass"] is True
    assert not result["failed_rules"]


def test_gate_fail_rule(tmp_path: Path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: 1
fail:
  - metric: pct_high_risk_queries
    op: ">"
    value: 1
""",
        encoding="utf-8",
    )
    policy = load_gate_policy(policy_path)
    result = evaluate_gate(compare_data=_compare_payload(), policy_data=policy, policy_dir=tmp_path)
    assert result["pass"] is False
    assert result["failed_rules"]


def test_gate_golden_failure(tmp_path: Path):
    golden_path = tmp_path / "golden.jsonl"
    golden_path.write_text(
        '{"name":"must-stay","params":{"q":"a"},"expected_ids":["MISS"]}\n',
        encoding="utf-8",
    )
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: 1
golden_queries:
  enabled: true
  file: "golden.jsonl"
  requirements:
    must_contain_topk: 10
    max_missing_pct: 0.0
""",
        encoding="utf-8",
    )
    policy = load_gate_policy(policy_path)
    result = evaluate_gate(compare_data=_compare_payload(), policy_data=policy, policy_dir=tmp_path)
    assert result["pass"] is False
    assert result["golden"]["failed"] is True


def test_gate_golden_empty_expected_is_skipped(tmp_path: Path):
    golden_path = tmp_path / "golden.jsonl"
    golden_path.write_text(
        '{"name":"skip","params":{"q":"a"},"expected_ids":[]}\n',
        encoding="utf-8",
    )
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: 1
golden_queries:
  enabled: true
  file: "golden.jsonl"
""",
        encoding="utf-8",
    )
    policy = load_gate_policy(policy_path)
    result = evaluate_gate(compare_data=_compare_payload(), policy_data=policy, policy_dir=tmp_path)
    assert result["pass"] is True
    assert result["golden"]["results"][0]["status"] == "SKIP"


def test_gate_segment_metric(tmp_path: Path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: 1
fail:
  - metric: pct_high_risk_queries_segment
    op: ">"
    value: 10
    args:
      segment_key: tenant
      segment_value: t1
""",
        encoding="utf-8",
    )
    payload = _compare_payload()
    payload["segments"] = {
        "by_segment": {
            "tenant:t1": {"high_risk_percent": 50.0}
        }
    }
    policy = load_gate_policy(policy_path)
    result = evaluate_gate(compare_data=payload, policy_data=policy, policy_dir=tmp_path)
    assert result["pass"] is False
    assert result["failed_rules"]
