from schema_lens.changesets.apply_schema import (
    apply_schema_operations,
    prepare_field_type_replace_updates,
    prepare_field_update,
    prepare_remove_filter_field_type,
)


def baseline_schema():
    return {
        "schema": {
            "fields": [
                {"name": "id", "type": "string", "stored": True, "indexed": True},
                {"name": "title", "type": "text_general", "stored": True, "indexed": True},
                {"name": "text", "type": "text_general", "stored": False, "indexed": True},
            ],
            "fieldTypes": [
                {
                    "name": "text_general",
                    "class": "solr.TextField",
                    "analyzer": {
                        "tokenizer": {"class": "solr.StandardTokenizerFactory"},
                        "filters": [
                            {"class": "solr.LowerCaseFilterFactory"},
                            {"class": "solr.EdgeNGramFilterFactory"},
                        ],
                    },
                },
                {"name": "text_en", "class": "solr.TextField"},
            ],
        }
    }


def test_prepare_field_update_merges_properties():
    schema = baseline_schema()
    op = {"op": "schema.field.update", "field": "title", "set": {"type": "text_en"}}
    payload = prepare_field_update(schema, op)
    assert payload["name"] == "title"
    assert payload["type"] == "text_en"
    assert payload["stored"] is True


def test_prepare_field_type_replace_updates_fields():
    schema = baseline_schema()
    op = {"op": "schema.fieldType.replace", "name": "text_general", "with": "text_en"}
    payloads = prepare_field_type_replace_updates(schema, op)
    assert len(payloads) == 2
    assert all(p["type"] == "text_en" for p in payloads)


def test_prepare_remove_filter_field_type_removes_matching_filter():
    schema = baseline_schema()
    op = {
        "op": "schema.analyzer.remove_filter",
        "fieldType": "text_general",
        "analyzer": "index",
        "filter_class": "solr.EdgeNGramFilterFactory",
    }
    payload = prepare_remove_filter_field_type(schema, op)
    classes = [f["class"] for f in payload["analyzer"]["filters"]]
    assert "solr.EdgeNGramFilterFactory" not in classes
    assert "solr.LowerCaseFilterFactory" in classes


def test_prepare_remove_filter_matches_short_name_filters():
    schema = {
        "schema": {
            "fields": [{"name": "title", "type": "text_general"}],
            "fieldTypes": [
                {
                    "name": "text_general",
                    "class": "solr.TextField",
                    "indexAnalyzer": {
                        "tokenizer": {"name": "standard"},
                        "filters": [
                            {"name": "stop"},
                            {"name": "lowercase"},
                        ],
                    },
                }
            ],
        }
    }

    op = {
        "op": "schema.analyzer.remove_filter",
        "fieldType": "text_general",
        "analyzer": "index",
        "filter_class": "solr.LowerCaseFilterFactory",
    }
    payload = prepare_remove_filter_field_type(schema, op)
    names = [f["name"] for f in payload["indexAnalyzer"]["filters"]]
    assert "lowercase" not in names
    assert "stop" in names


def test_apply_schema_operations_skips_missing_remove_filter(monkeypatch):
    schema = {
        "schema": {
            "fields": [{"name": "title", "type": "text_general"}],
            "fieldTypes": [
                {
                    "name": "text_general",
                    "class": "solr.TextField",
                    "indexAnalyzer": {
                        "tokenizer": {"name": "standard"},
                        "filters": [{"name": "stop"}],
                    },
                }
            ],
        }
    }
    calls = {"replace_field_type": 0}

    def fake_replace_field_type(*_args, **_kwargs):
        calls["replace_field_type"] += 1

    monkeypatch.setattr(
        "schema_lens.solr.schema_api.replace_field_type",
        fake_replace_field_type,
    )

    out = apply_schema_operations(
        client=object(),
        shadow_collection="shadow",
        baseline_schema=schema,
        changes=[
            {
                "op": "schema.analyzer.remove_filter",
                "fieldType": "text_general",
                "analyzer": "index",
                "filter_class": "solr.LowerCaseFilterFactory",
            }
        ],
    )

    assert calls["replace_field_type"] == 0
    assert out[0]["skipped"] is True
