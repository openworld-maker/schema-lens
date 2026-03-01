from schema_lens.changesets.model import Changeset
from schema_lens.changesets.validator import validate_changeset


def test_validator_accepts_minimal_valid_changeset(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text('q=foo\n', encoding="utf-8")

    data = {
        "schema_lens_version": 1,
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": str(docs)}},
        "queries": {"source": {"path": str(queries)}},
        "changes": [{"op": "queryparams.set", "set": {"qf": "title^2"}}],
    }

    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok
    assert report.warnings == []


def test_validator_reports_missing_required_fields():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr"},
        "changes": [{"op": "queryparams.set", "set": {"qf": "x"}}],
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("baseline.collection" in err for err in report.errors)
    assert any("data.docs_source.path" in err for err in report.errors)


def test_validator_rejects_unknown_op():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [{"op": "schema.unknown"}],
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("unsupported" in err for err in report.errors)


def test_validator_detects_malformed_operation_payload():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [{"op": "schema.field.update", "field": "title", "set": "not-an-object"}],
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("set must be an object" in err for err in report.errors)


def test_validator_rejects_unsupported_version():
    data = {
        "schema_lens_version": 99,
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [],
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("Unsupported schema_lens_version" in err for err in report.errors)


def test_validator_accepts_solr_doc_source_without_path(tmp_path):
    queries = tmp_path / "queries.log"
    queries.write_text("q=foo\n", encoding="utf-8")
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {
            "docs_source": {
                "type": "solr",
                "solr_url": "http://localhost:8983/solr",
                "collection": "products",
                "mode": "cursormark",
            }
        },
        "queries": {"source": {"type": "log", "path": str(queries), "format": "solr_params"}},
        "changes": [],
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_accepts_replay_capture_config(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "replay": {
            "capture": {
                "facets": {"enabled": True, "fields": ["category"], "limit": 20},
                "track_numfound": True,
                "track_sort": True,
            }
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_replay_capture_fields(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "replay": {
            "capture": {
                "facets": {"enabled": True, "fields": "bad", "limit": 0},
                "track_numfound": "yes",
            }
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert not report.ok
    assert any("replay.capture.facets.fields" in err for err in report.errors)
