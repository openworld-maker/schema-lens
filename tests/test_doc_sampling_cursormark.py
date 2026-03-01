from schema_lens.data.cursormark import sample_docs_cursormark


def test_cursormark_sampling_paginates_and_stops(monkeypatch):
    responses = [
        {"response": {"docs": [{"id": "1"}, {"id": "2"}]}, "nextCursorMark": "abc"},
        {"response": {"docs": [{"id": "3"}]}, "nextCursorMark": "abc"},
    ]
    calls = {"i": 0}

    def fake_select(_client, _collection, _params):
        i = calls["i"]
        calls["i"] += 1
        return responses[i]

    monkeypatch.setattr("schema_lens.data.cursormark.select", fake_select)
    docs = sample_docs_cursormark(
        client=object(),
        collection="products",
        query="*:*",
        fl="id",
        sort="id asc",
        sample_n=10,
        batch_size=2,
    )
    assert [d["id"] for d in docs] == ["1", "2", "3"]


def test_cursormark_sampling_respects_sample_n(monkeypatch):
    def fake_select(_client, _collection, _params):
        return {
            "response": {"docs": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
            "nextCursorMark": "next",
        }

    monkeypatch.setattr("schema_lens.data.cursormark.select", fake_select)
    docs = sample_docs_cursormark(
        client=object(),
        collection="products",
        query="*:*",
        fl="id",
        sort="id asc",
        sample_n=2,
        batch_size=100,
    )
    assert [d["id"] for d in docs] == ["1", "2"]

