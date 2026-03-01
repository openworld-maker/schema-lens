from schema_lens.compare.facets import compute_facet_diff


def test_compute_facet_diff_new_missing_and_deltas():
    out = compute_facet_diff(
        baseline={"category": {"tools": 10, "hardware": 5}},
        shadow={"category": {"tools": 7, "newcat": 3}},
    )
    section = out["category"]
    assert "newcat" in section["new_values"]
    assert "hardware" in section["missing_values"]
    top = section["top_deltas"][0]
    assert top["value"] in {"tools", "hardware", "newcat"}

