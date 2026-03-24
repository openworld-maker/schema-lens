import json
from pathlib import Path

from typer.testing import CliRunner

from schema_lens.cli import app
from schema_lens.compat import capabilities_for_version, compatibility_contract, detect_solr_version
from schema_lens.compat.adapters import (
    extract_explain_debug,
    configset_upload_supported,
    hybrid_mode,
    metrics_supported,
    preferred_metrics_source,
    structured_explain_supported,
    vector_supported,
)
from schema_lens.compat.detect import detect_version_info


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
    assert caps8["vector_supported"] is False
    assert caps9["vector_native_hybrid_supported"] is True


def test_unknown_version_degrades_safely():
    caps = capabilities_for_version(None)
    assert caps["version_detected"] is False
    assert metrics_supported(caps)
    assert caps["vector_supported"] is False


def test_compatibility_contract_contains_missing_and_fallbacks():
    contract = compatibility_contract("8.11.2")
    assert contract["support_tier"] == "supported_with_fallbacks"
    assert "vector_supported" in contract["missing_capabilities"]
    assert any(item["feature"] == "vector_hybrid" for item in contract["fallbacks"])
    assert contract["version"]["major"] == 8


def test_detect_version_info_with_mode_and_node():
    payload = {
        "mode": "solrcloud",
        "node": "solr-1",
        "lucene": {"solr-impl-version": "Apache Solr 9.8.1 abc"},
    }
    info = detect_version_info(payload)
    assert info.version_string == "9.8.1"
    assert info.deployment_mode == "solrcloud"
    assert info.node_name == "solr-1"


def test_metrics_adapter_prefers_json_then_mbeans():
    caps = {"metrics_json_supported": True, "metrics_mbeans_supported": True}
    assert preferred_metrics_source(caps) == "metrics"
    caps = {"metrics_json_supported": False, "metrics_mbeans_supported": True}
    assert preferred_metrics_source(caps) == "mbeans"
    caps = {"metrics_json_supported": False, "metrics_mbeans_supported": False}
    assert preferred_metrics_source(caps) == "unavailable"


def test_explain_adapter_extracts_both_shapes():
    payload_v1 = {
        "debug": {
            "parsedquery_toString": "name:bolt",
            "explain": {"doc1": "score"},
        }
    }
    out_v1 = extract_explain_debug(payload_v1)
    assert out_v1["parsedquery"] == "name:bolt"
    assert isinstance(out_v1["structured_explain"], dict)

    payload_v2 = {
        "parsedquery_toString": "name:bolt",
        "explain": [{"doc1": {"value": 1.0}}],
    }
    out_v2 = extract_explain_debug(payload_v2)
    assert out_v2["parsedquery"] == "name:bolt"
    assert out_v2["structured_explain"]["doc1"]["value"] == 1.0


def test_vector_adapter_hybrid_mode():
    assert hybrid_mode({"vector_supported": False}) == "disabled"
    assert hybrid_mode({"vector_supported": True, "vector_native_hybrid_supported": False}) == "client_side"
    assert hybrid_mode({"vector_supported": True, "vector_native_hybrid_supported": True}) == "native"


def test_detect_capabilities_cli_from_fixture(tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "caps.json"
    result = runner.invoke(
        app,
        [
            "detect-capabilities",
            "--from-file",
            "examples/compat/solr9_system_info.json",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    payload = out.read_text(encoding="utf-8")
    assert "recommended" in payload
    assert "vector_search" in payload


def test_compatibility_cli_from_fixture():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "compatibility",
            "--from-file",
            "examples/compat/solr10_system_info.json",
        ],
    )
    assert result.exit_code == 0
    assert "forward_ready" in result.stdout


def test_fixture_based_contracts_for_solr8_9_10():
    for fixture, expected_tier in (
        ("examples/compat/fixtures/solr8_system_info.json", "supported_with_fallbacks"),
        ("examples/compat/fixtures/solr9_system_info.json", "recommended"),
        ("examples/compat/fixtures/solr10_system_info.json", "forward_ready"),
    ):
        payload = Path(fixture)
        data = json.loads(payload.read_text(encoding="utf-8"))
        contract = compatibility_contract(
            detect_version_info(data),
            system_info=data,
        )
        assert contract["support_tier"] == expected_tier
