from schema_lens.ltr.capture import capture_ltr_impact
from schema_lens.ltr.detect import detect_ltr_params
from schema_lens.ltr.diff import diff_feature_maps, parse_feature_string


def test_detect_ltr_params_and_parse_features():
    assert detect_ltr_params({"rq": "{!ltr model=my_model}"}) is True
    assert detect_ltr_params({"fl": "id,score,[features store=my_store]"}) is True
    assert detect_ltr_params({"q": "bolt"}) is False
    parsed = parse_feature_string("title_bm25=1.5, click_prior=0.2")
    assert parsed == {"title_bm25": 1.5, "click_prior": 0.2}


def test_capture_ltr_impact_and_feature_diff():
    deltas = diff_feature_maps({"a": 1.0, "b": 2.0}, {"a": 1.5, "c": 3.0})
    assert deltas[0]["feature"] in {"b", "c"}

    replay_data = {
        "pairs": [
            {
                "query": {"id": 1},
                "effective_params": {"rq": "{!ltr model=my_model}", "fl": "id,score,[features]"},
                "baseline": {"docs": [{"id": "A", "[features]": "title=1.0, prior=0.2"}]},
                "shadow": {"docs": [{"id": "A", "[features]": "title=1.4, prior=0.2"}]},
            }
        ]
    }
    impact = capture_ltr_impact(replay_data)
    assert impact["enabled"] is True
    assert impact["queries_analyzed"] == 1
    assert impact["feature_drift_count"] == 1
