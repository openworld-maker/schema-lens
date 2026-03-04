import pytest

from schema_lens.errors import SolrRequestError
from schema_lens.shadow.manager import cleanup_shadow, create_shadow


def test_create_shadow_isolated_success(monkeypatch):
    monkeypatch.setattr("schema_lens.shadow.manager.render_shadow_name", lambda *_: "shadow1")
    monkeypatch.setattr("schema_lens.shadow.manager.collection_config_name", lambda *_: "cfg0")

    calls = {"create_configset": 0, "create_collection": 0}

    def fake_create_configset(*_args, **_kwargs):
        calls["create_configset"] += 1

    def fake_create_collection(*_args, **kwargs):
        calls["create_collection"] += 1
        assert kwargs["config_name"] == "shadow1__cfg"

    monkeypatch.setattr("schema_lens.shadow.manager.create_configset", fake_create_configset)
    monkeypatch.setattr("schema_lens.shadow.manager.create_collection", fake_create_collection)
    monkeypatch.setattr(
        "schema_lens.shadow.manager.apply_schema_operations",
        lambda *_args, **_kwargs: [{"op": "schema.field.update"}],
    )

    manifest = create_shadow(
        client=object(),
        baseline_collection="products",
        baseline_solr_url="http://baseline",
        shadow_solr_url="http://shadow",
        shadow_cfg={},
        baseline_schema={"schema": {}},
        changes=[],
    )

    assert calls["create_configset"] == 1
    assert calls["create_collection"] == 1
    assert manifest.configset_isolated is True
    assert manifest.shadow_configset == "shadow1__cfg"


def test_create_shadow_fallback_when_allowed(monkeypatch):
    monkeypatch.setattr("schema_lens.shadow.manager.render_shadow_name", lambda *_: "shadow2")
    monkeypatch.setattr("schema_lens.shadow.manager.collection_config_name", lambda *_: "cfg0")

    def fail_create_configset(*_args, **_kwargs):
        raise SolrRequestError("denied")

    captured = {}

    def fake_create_collection(*_args, **kwargs):
        captured["config_name"] = kwargs["config_name"]

    monkeypatch.setattr("schema_lens.shadow.manager.create_configset", fail_create_configset)
    monkeypatch.setattr("schema_lens.shadow.manager.create_collection", fake_create_collection)
    monkeypatch.setattr("schema_lens.shadow.manager.apply_schema_operations", lambda *_a, **_k: [])

    manifest = create_shadow(
        client=object(),
        baseline_collection="products",
        baseline_solr_url="http://baseline",
        shadow_solr_url="http://shadow",
        shadow_cfg={"allow_shared_configset_fallback": True},
        baseline_schema={"schema": {}},
        changes=[],
    )

    assert captured["config_name"] == "cfg0"
    assert manifest.configset_isolated is False
    assert manifest.shadow_configset == "cfg0"
    assert manifest.warnings


def test_create_shadow_raises_when_fallback_disallowed(monkeypatch):
    monkeypatch.setattr("schema_lens.shadow.manager.render_shadow_name", lambda *_: "shadow3")
    monkeypatch.setattr("schema_lens.shadow.manager.collection_config_name", lambda *_: "cfg0")

    def fail_create_configset(*_args, **_kwargs):
        raise SolrRequestError("denied")

    monkeypatch.setattr("schema_lens.shadow.manager.create_configset", fail_create_configset)

    with pytest.raises(SolrRequestError):
        create_shadow(
            client=object(),
            baseline_collection="products",
            baseline_solr_url="http://baseline",
            shadow_solr_url="http://shadow",
            shadow_cfg={"allow_shared_configset_fallback": False},
            baseline_schema={"schema": {}},
            changes=[],
        )


def test_cleanup_shadow_deletes_collection_and_optional_configset(monkeypatch):
    monkeypatch.setattr("schema_lens.shadow.manager.delete_collection", lambda *_: {"ok": True})
    monkeypatch.setattr(
        "schema_lens.shadow.manager.delete_configset",
        lambda *_: {"cfg": "deleted"},
    )

    out = cleanup_shadow(object(), "shadow-x", shadow_configset="cfg-x")
    assert out["collection"]["ok"] is True
    assert out["configset"]["cfg"] == "deleted"


def test_create_shadow_with_configset_updates_uploads_patched_configset(monkeypatch, tmp_path):
    monkeypatch.setattr("schema_lens.shadow.manager.render_shadow_name", lambda *_: "shadow4")
    monkeypatch.setattr("schema_lens.shadow.manager.collection_config_name", lambda *_: "cfg0")
    monkeypatch.setattr("schema_lens.shadow.manager.has_configset_updates", lambda *_: True)

    cfg_root = tmp_path / "cfg"
    (cfg_root / "conf").mkdir(parents=True)
    (cfg_root / "conf/synonyms.txt").write_text("ss=>steel\n", encoding="utf-8")

    monkeypatch.setattr(
        "schema_lens.shadow.manager._materialize_baseline_configset",
        lambda **_kwargs: cfg_root,
    )
    monkeypatch.setattr(
        "schema_lens.shadow.manager.apply_configset_updates",
        lambda **_kwargs: {"applied": [{"op": "schema.synonym.update"}]},
    )

    hashes = iter(["sha256:base", "sha256:shadow"])
    monkeypatch.setattr("schema_lens.shadow.manager.hash_directory", lambda *_: next(hashes))
    captured = {}

    def fake_upload(*_args, **kwargs):
        captured["name"] = kwargs["name"]
        return {"ok": True}

    monkeypatch.setattr("schema_lens.shadow.manager.upload_configset_from_dir", fake_upload)
    monkeypatch.setattr(
        "schema_lens.shadow.manager.create_configset",
        lambda *_a, **_k: {"ok": True},
    )
    monkeypatch.setattr(
        "schema_lens.shadow.manager.delete_configset",
        lambda *_a, **_k: {"ok": True},
    )
    monkeypatch.setattr(
        "schema_lens.shadow.manager.create_collection",
        lambda *_a, **_k: {"ok": True},
    )
    monkeypatch.setattr("schema_lens.shadow.manager.apply_schema_operations", lambda *_a, **_k: [])

    manifest = create_shadow(
        client=object(),
        baseline_collection="products",
        baseline_solr_url="http://baseline",
        shadow_solr_url="http://shadow",
        shadow_cfg={},
        baseline_schema={"schema": {}},
        changes=[{"op": "schema.synonym.update"}],
    )

    assert captured["name"] == "shadow4__cfg"
    assert manifest.baseline_configset_hash == "sha256:base"
    assert manifest.shadow_configset_hash == "sha256:shadow"
    assert manifest.shadow_configset == "shadow4__cfg__trusted"
    assert manifest.configset_patch["applied"][0]["op"] == "schema.synonym.update"
