from schema_lens.changesets.apply_queryparams import merge_queryparams


def test_merge_queryparams_applies_queryparams_set_only():
    base = {"rows": 10, "fl": "id,score", "qf": "title^2"}
    changes = [
        {"op": "schema.field.update", "field": "title", "set": {"stored": True}},
        {"op": "queryparams.set", "set": {"qf": "title^5 text", "pf": "title^20"}},
    ]

    out = merge_queryparams(base, changes)
    assert out["rows"] == 10
    assert out["qf"] == "title^5 text"
    assert out["pf"] == "title^20"


def test_merge_queryparams_ignores_non_dict_set():
    base = {"rows": 10}
    changes = [{"op": "queryparams.set", "set": "bad"}]
    out = merge_queryparams(base, changes)
    assert out == base
