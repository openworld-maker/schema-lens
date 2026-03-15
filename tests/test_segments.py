from schema_lens.segments import build_segment_report


def test_segment_report_aggregation_and_policy():
    compare_data = {
        "diffs": [
            {"segment": {"tenant": "t1", "region": "us"}, "overlap_ratio": 0.8, "risk_severity": "LOW"},
            {"segment": {"tenant": "t1", "region": "us"}, "overlap_ratio": 0.4, "risk_severity": "HIGH"},
            {"segment": {"tenant": "t2", "region": "eu"}, "overlap_ratio": 0.9, "risk_severity": "LOW"},
        ]
    }
    policy = {
        "rules": [
            {
                "segment_key": "tenant",
                "segment_value": "t1",
                "metric": "high_risk_percent",
                "op": ">",
                "value": 10,
                "severity": "fail",
            }
        ]
    }
    report = build_segment_report(compare_data=compare_data, policy=policy)
    assert report["enabled"] is True
    assert report["by_segment"]["tenant:t1"]["queries_total"] == 2
    assert report["policy"]["pass"] is False
