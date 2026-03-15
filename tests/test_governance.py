from __future__ import annotations

from schema_lens.governance import (
    merge_policy_bundles,
    normalize_approval_metadata,
    sign_manifest,
    validate_exception_records,
    validate_promotion_state,
    validate_transition,
    verify_manifest_signature,
)


def test_approval_metadata_normalization():
    payload = normalize_approval_metadata({"requested_by": "alice", "ticket_id": 123})
    assert payload["requested_by"] == "alice"
    assert payload["ticket_id"] == "123"


def test_exception_records_validation():
    records = validate_exception_records(
        [{"id": "ex-1", "rationale": "temporary", "expiry": "2099-01-01T00:00:00Z"}]
    )
    assert records[0]["expired"] is False


def test_promotion_state_and_transition():
    assert validate_promotion_state("dev") == "dev"
    validate_transition("dev", "stage")


def test_policy_bundle_merge(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("fail:\n  - metric: avg_overlap\n", encoding="utf-8")
    b.write_text("warn:\n  - metric: pct_high_risk_queries\n", encoding="utf-8")
    merged = merge_policy_bundles([a, b])
    assert len(merged["fail"]) == 1
    assert len(merged["warn"]) == 1


def test_manifest_sign_and_verify():
    manifest = {"run_id": "r1", "stats": {"duration_seconds": 1.2}}
    secret = "top-secret"
    signature = sign_manifest(manifest, secret)
    assert verify_manifest_signature(manifest, secret, signature)
