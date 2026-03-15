from schema_lens.compat import capabilities_for_version, detect_solr_version
from schema_lens.compat.adapters import (
    configset_upload_supported,
    metrics_supported,
    structured_explain_supported,
    vector_supported,
)


def test_detect_solr_version_from_lucene_payload():
    payload = {"lucene": {"solr-spec-version": "9.7.0"}}
    assert detect_solr_version(payload) == "9.7.0"


def test_detect_solr_version_from_impl_string():
    payload = {"lucene": {"solr-impl-version": "Apache Solr 10.0.1 abc"}}
    assert detect_solr_version(payload) == "10.0.1"


def test_capability_matrix_for_solr8_9_10():
    caps8 = capabilities_for_version("8.11.2")
    caps9 = capabilities_for_version("9.7.0")
    caps10 = capabilities_for_version("10.0.0")

    assert not vector_supported(caps8)
    assert vector_supported(caps9)
    assert vector_supported(caps10)

    assert not structured_explain_supported(caps8)
    assert structured_explain_supported(caps9)

    assert metrics_supported(caps10)
    assert configset_upload_supported(caps8)
    assert caps10["metrics_prometheus_default"] is True


def test_unknown_version_degrades_safely():
    caps = capabilities_for_version(None)
    assert caps["version_detected"] is False
    assert metrics_supported(caps)
