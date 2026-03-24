from pathlib import Path

from schema_lens.privacy import (
    build_privacy_report,
    enforce_retention,
    mask_payload,
    resolve_privacy_profile,
)


def test_mask_payload_deterministic():
    payload = {
        "email": "alice@example.com",
        "uuid": "123e4567-e89b-12d3-a456-426614174000",
        "text": "order 123456 for alice@example.com",
    }
    masked = mask_payload(
        payload,
        salt="s1",
        email=True,
        uuid=True,
        numeric_id_hash=True,
        allowlist=None,
        denylist=None,
    )
    assert "<email_masked>" in masked["text"]
    assert "<id_" in masked["text"]


def test_retention_deletes_sensitive_artifacts(tmp_path: Path):
    for name in ("docs_sample.jsonl", "queries_extracted.jsonl", "replay.json"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    deleted = enforce_retention(tmp_path, persist_sensitive=False)
    assert set(deleted) == {"docs_sample.jsonl", "queries_extracted.jsonl", "replay.json"}


def test_retention_summary_only_deletes_detail_artifacts(tmp_path: Path):
    for name in ("compare.json", "report.json", "replay.json", "rootcauses.json"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    deleted = enforce_retention(tmp_path, persist_sensitive=False, summary_only=True)
    assert "compare.json" in deleted
    assert "replay.json" in deleted
    assert "rootcauses.json" in deleted
    assert not (tmp_path / "compare.json").exists()
    # report.json remains for summary-only sharing
    assert (tmp_path / "report.json").exists()


def test_privacy_profile_and_report():
    profile = resolve_privacy_profile("export-safe")
    assert profile.export_safe is True
    report = build_privacy_report(
        profile=profile.name,
        masked_fields=["email"],
        dropped_fields=["docs_sample.jsonl"],
        retention_deleted=["replay.json"],
        export_safe=True,
    )
    assert report["enabled"] is True
    assert report["profile"] == "export-safe"
