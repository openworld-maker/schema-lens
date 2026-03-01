from schema_lens.data.solr_export import sample_docs_export
from schema_lens.data.solr_sampler import sample_docs_from_solr


class _Client:
    def __init__(self, payload):
        self.payload = payload

    def get_json(self, _path, params=None):
        _ = params
        return self.payload


def test_export_sampling_success():
    docs = sample_docs_export(
        client=_Client({"response": {"docs": [{"id": "1"}, {"id": "2"}]}}),
        collection="products",
        query="*:*",
        fl="id",
        sort="id asc",
        sample_n=10,
    )
    assert [d["id"] for d in docs] == ["1", "2"]


def test_export_fallback_to_cursormark(monkeypatch):
    class FailingClient:
        def get_json(self, _path, params=None):
            _ = params
            raise RuntimeError("export unavailable")

    monkeypatch.setattr(
        "schema_lens.data.solr_sampler.sample_docs_cursormark",
        lambda **_kwargs: [{"id": "c1"}],
    )
    docs, mode = sample_docs_from_solr(
        client=FailingClient(),
        collection="products",
        mode="export",
        query="*:*",
        fl="id",
        sort="id asc",
        sample_n=1,
    )
    assert mode == "cursormark"
    assert docs == [{"id": "c1"}]

