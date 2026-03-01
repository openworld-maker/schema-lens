from pathlib import Path

from schema_lens.snapshot.snapshotter import capture_snapshot, load_snapshot, snapshot_hash


def test_snapshot_hash_is_deterministic():
    payload = {
        "solr_url": "http://localhost:8983/solr",
        "collection": "products",
        "schema": {"schema": {"fields": [{"name": "id", "type": "string"}]}},
        "system": {"lucene": {"solr-spec-version": "9.7.0"}},
        "collection_state": {"cluster": {"collections": {"products": {}}}},
        "request_defaults": {"defType": "edismax"},
    }
    h1 = snapshot_hash(**payload)
    h2 = snapshot_hash(**payload)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_capture_snapshot_writes_files(monkeypatch, tmp_path: Path):
    class _FakeClient:
        def close(self):
            return None

    monkeypatch.setattr(
        "schema_lens.snapshot.snapshotter.SolrHttpClient",
        lambda *_a, **_k: _FakeClient(),
    )
    monkeypatch.setattr(
        "schema_lens.snapshot.snapshotter.get_schema",
        lambda *_a, **_k: {"schema": {"fields": [{"name": "id", "type": "string"}]}},
    )
    monkeypatch.setattr(
        "schema_lens.snapshot.snapshotter.system_info",
        lambda *_a, **_k: {"lucene": {"solr-spec-version": "9.7.0"}},
    )
    monkeypatch.setattr(
        "schema_lens.snapshot.snapshotter.cluster_status",
        lambda *_a, **_k: {"cluster": {"collections": {"products": {}}}},
    )

    capture_snapshot(
        solr_url="http://localhost:8983/solr",
        collection="products",
        out_dir=tmp_path,
        request_defaults={"defType": "edismax"},
    )
    assert (tmp_path / "snapshot.json").exists()
    assert (tmp_path / "snapshot.schema.json").exists()
    assert (tmp_path / "snapshot.system.json").exists()
    assert (tmp_path / "snapshot.collection.json").exists()
    assert (tmp_path / "snapshot.hash.txt").exists()

    loaded = load_snapshot(tmp_path)
    assert loaded["hash"].startswith("sha256:")
