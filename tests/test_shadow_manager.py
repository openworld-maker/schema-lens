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
