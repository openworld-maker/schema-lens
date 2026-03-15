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


def test_validator_accepts_synonym_stopwords_and_rewrite_diff(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    synonyms = tmp_path / "synonyms_v2.txt"
    stopwords = tmp_path / "stopwords_v2.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")
    synonyms.write_text("ss=>stainless steel\n", encoding="utf-8")
    stopwords.write_text("the\nand\n", encoding="utf-8")
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [
            {
                "op": "schema.synonym.update",
                "mode": "replace",
                "source_file": str(synonyms),
                "target": {"files": [{"path": "conf/synonyms.txt"}]},
            },
            {
                "op": "schema.stopwords.update",
                "mode": "patch_merge",
                "source_file": str(stopwords),
                "target": {"files": [{"path": "conf/stopwords.txt"}]},
            },
        ],
        "evaluation": {
            "rewrite_diff": {
                "enabled": True,
                "max_queries": 10,
                "debug_mode": "results",
                "clause_spike_threshold": 3,
                "always_for_high_risk": True,
            }
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_configset_op_shapes(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [
            {
                "op": "schema.synonym.update",
                "mode": "bad_mode",
                "target": {"files": [{"path": "conf/synonyms.txt"}]},
            }
        ],
        "evaluation": {
            "rewrite_diff": {
                "enabled": "yes",
                "debug_mode": "unknown",
            }
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert not report.ok
    assert any(".mode must be one of" in err for err in report.errors)
    assert any("evaluation.rewrite_diff.enabled" in err for err in report.errors)


def test_validator_accepts_vector_hybrid_sections(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.jsonl"
    embeddings = tmp_path / "embeddings.jsonl"
    docs.write_text('{"id":"1","emb":[0.1,0.2,0.3,0.4]}\n', encoding="utf-8")
    queries.write_text(
        '{"params":{"q":"bolt"},"vector":[0.1,0.2,0.3,0.4]}\n',
        encoding="utf-8",
    )
    embeddings.write_text('{"id":"1","emb":[0.1,0.2,0.3,0.4]}\n', encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs), "format": "jsonl"}},
        "queries": {"source": {"type": "file", "path": str(queries), "format": "jsonl"}},
        "changes": [{"op": "queryparams.set", "set": {"qf": "title^2"}}],
        "vector": {
            "enabled": True,
            "field": "emb",
            "dimension": 4,
            "similarity": "cosine",
            "query_vector_policy": "skip",
            "embedding_source": {"type": "file", "path": str(embeddings)},
            "scenarios": [
                {"name": "lexical_only", "mode": "lexical_only"},
                {"name": "vector_only", "mode": "vector_only", "knn": {"k": 20, "topK": 10}},
                {
                    "name": "hybrid",
                    "mode": "hybrid",
                    "knn": {"k": 20, "topK": 10},
                    "blend": {"method": "linear", "execution": "client"},
                },
            ],
        },
        "evaluation": {
            "vector_hybrid": {
                "enabled": True,
                "topK": 10,
                "candidate_pool": 50,
                "sensitivity": {"enabled": True, "weights": [0.9, 0.7]},
            }
        },
    }

    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_vector_sections(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "vector": {
            "enabled": True,
            "field": "",
            "similarity": "bad",
            "query_vector_policy": "maybe",
            "scenarios": [{"name": "bad", "mode": "hybrid", "blend": {"method": "unknown"}}],
        },
        "evaluation": {"vector_hybrid": {"topK": 0, "sensitivity": {"weights": ["x"]}}},
    }

    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert not report.ok
    assert any("vector.field" in err for err in report.errors)
    assert any("vector.similarity" in err for err in report.errors)
    assert any("vector.query_vector_policy" in err for err in report.errors)
    assert any("evaluation.vector_hybrid.topK" in err for err in report.errors)


def test_validator_accepts_security_profiles_and_auth(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "security": {
            "profile": "enterprise-safe",
            "baseline_auth": {"type": "basic", "username": "u", "password": "p"},
            "shadow_auth": {"type": "bearer", "token_env": "TEST_TOKEN"},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_security_auth():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [],
        "security": {
            "profile": "bad-profile",
            "baseline_auth": {"type": "unknown"},
            "shadow_auth": {"type": "plugin"},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("security.profile" in err for err in report.errors)
    assert any("security.baseline_auth.type" in err for err in report.errors)
    assert any("requires provider plugin name" in err for err in report.errors)


def test_validator_accepts_observability_sections(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "observability": {
            "enabled": True,
            "prometheus": {"enabled": True},
            "otel": {"enabled": True},
            "webhooks": {"enabled": True, "urls": ["http://localhost:9000/events"]},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_observability_sections():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [],
        "observability": {
            "enabled": "yes",
            "prometheus": "bad",
            "webhooks": {"enabled": "true", "urls": "http://x"},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("observability.enabled" in err for err in report.errors)
    assert any("observability.prometheus" in err for err in report.errors)
    assert any("observability.webhooks.urls" in err for err in report.errors)


def test_validator_accepts_governance_sections(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")

    bundle = tmp_path / "bundle.yaml"
    bundle.write_text("fail: []\nwarn: []\n", encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "governance": {
            "enabled": True,
            "approval": {"requested_by": "alice", "ticket_id": "ABC-1"},
            "promotion_state": "stage",
            "exceptions": [
                {
                    "id": "ex1",
                    "rationale": "known issue",
                    "expiry": "2099-01-01T00:00:00Z",
                }
            ],
            "policy_bundles": [str(bundle)],
            "signing": {"enabled": True, "secret": "secret"},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_governance_sections():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [],
        "governance": {
            "enabled": True,
            "approval": {},
            "promotion_state": "bad",
            "policy_bundles": "x",
            "signing": {"enabled": True},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("governance.approval.requested_by" in err for err in report.errors)
    assert any("governance.promotion_state" in err for err in report.errors)
    assert any("governance.policy_bundles" in err for err in report.errors)


def test_validator_accepts_segments_config(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.jsonl"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text('{"params":{"q":"foo"},"segment":{"tenant":"t1"}}\n', encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries), "format": "jsonl"}},
        "changes": [],
        "segments": {
            "enabled": True,
            "keys": ["tenant", "region"],
            "policy": {"rules": []},
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_segments_config():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [],
        "segments": {
            "enabled": "yes",
            "keys": "tenant",
            "policy": "bad",
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("segments.enabled" in err for err in report.errors)
    assert any("segments.keys" in err for err in report.errors)
    assert any("segments.policy" in err for err in report.errors)


def test_validator_accepts_privacy_config(tmp_path):
    docs = tmp_path / "docs.jsonl"
    queries = tmp_path / "queries.txt"
    docs.write_text('{"id":"1"}\n', encoding="utf-8")
    queries.write_text("q=foo\n", encoding="utf-8")

    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"type": "file", "path": str(docs)}},
        "queries": {"source": {"type": "file", "path": str(queries)}},
        "changes": [],
        "privacy": {
            "profile": "export-safe",
            "allowlist": ["summary"],
            "denylist": ["raw_docs"],
            "no_persist_sensitive": True,
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=True)
    assert report.ok


def test_validator_rejects_invalid_privacy_config():
    data = {
        "baseline": {"solr_url": "http://localhost:8983/solr", "collection": "products"},
        "data": {"docs_source": {"path": "docs.jsonl"}},
        "queries": {"source": {"path": "queries.txt"}},
        "changes": [],
        "privacy": {
            "profile": "bad",
            "allowlist": "x",
            "no_persist_sensitive": "yes",
        },
    }
    report = validate_changeset(Changeset(raw=data), check_paths=False)
    assert not report.ok
    assert any("privacy.profile" in err for err in report.errors)
    assert any("privacy.allowlist" in err for err in report.errors)
    assert any("privacy.no_persist_sensitive" in err for err in report.errors)
