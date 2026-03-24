from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.plugins.contracts.auth import AuthProviderPlugin
from schema_lens.security import REDACTED
from schema_lens.security.audit import build_audit_record
from schema_lens.security.auth import AuthResolutionError, resolve_auth_material
from schema_lens.security.profiles import resolve_profile
from schema_lens.security.redaction import redact_payload, redact_text, redact_url
from schema_lens.security.secrets import resolve_secret, resolve_secret_field


class _AuthPlugin(AuthProviderPlugin):
    metadata = type(
        "Meta",
        (),
        {
            "name": "custom_auth",
            "version": "0.1.0",
            "plugin_type": "auth",
            "capabilities": ["custom-auth"],
            "schema_lens_version": "*",
        },
    )()

    def build_auth(self, context):
        return {"headers": {"Authorization": "Custom abc"}}


def test_resolve_secret_env_file_and_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_USER", "alice")
    secret_file = tmp_path / "pw.txt"
    secret_file.write_text("s3cr3t\n", encoding="utf-8")

    assert resolve_secret("${SEC_USER}", base_dir=tmp_path) == "alice"
    assert resolve_secret(f"file:{secret_file}", base_dir=tmp_path) == "s3cr3t"
    assert resolve_secret({"from_env": "SEC_USER"}, base_dir=tmp_path) == "alice"
    assert resolve_secret({"from_file": str(secret_file)}, base_dir=tmp_path) == "s3cr3t"


def test_resolve_secret_missing_or_blank_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_SECRET", raising=False)
    with pytest.raises(ValueError):
        resolve_secret("${MISSING_SECRET}", base_dir=tmp_path)
    with pytest.raises(ValueError):
        resolve_secret("", base_dir=tmp_path)


def test_resolve_secret_field_env_and_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_USER", "alice")
    f = tmp_path / "pw.txt"
    f.write_text("s3cr3t\n", encoding="utf-8")

    cfg = {"username_env": "SEC_USER", "password_file": str(f)}
    assert resolve_secret_field(cfg, "username", base_dir=tmp_path) == "alice"
    assert resolve_secret_field(cfg, "password", base_dir=tmp_path) == "s3cr3t"


def test_auth_basic_and_bearer_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASIC_USER", "u")
    monkeypatch.setenv("BASIC_PASS", "p")
    monkeypatch.setenv("BEARER_TOKEN", "abc")

    basic = resolve_auth_material(
        {"type": "basic", "username": "${BASIC_USER}", "password": "${BASIC_PASS}"},
        base_dir=tmp_path,
    )
    assert basic.mode == "basic"
    assert basic.headers["Authorization"].startswith("Basic ")

    bearer = resolve_auth_material(
        {"type": "bearer", "token": "${BEARER_TOKEN}"},
        base_dir=tmp_path,
    )
    assert bearer.headers["Authorization"] == "Bearer abc"


def test_auth_mtls_resolution_and_missing_file(tmp_path: Path) -> None:
    cert = tmp_path / "client.pem"
    key = tmp_path / "client.key"
    ca = tmp_path / "ca.pem"
    cert.write_text("x", encoding="utf-8")
    key.write_text("y", encoding="utf-8")
    ca.write_text("z", encoding="utf-8")

    material = resolve_auth_material(
        {
            "type": "mtls",
            "cert_file": str(cert),
            "key_file": str(key),
            "ca_file": str(ca),
        },
        base_dir=tmp_path,
    )
    assert material.mode == "mtls"
    assert isinstance(material.cert, tuple)
    assert material.verify == str(ca)

    with pytest.raises(AuthResolutionError):
        resolve_auth_material(
            {
                "type": "mtls",
                "cert_file": str(tmp_path / "missing.pem"),
            },
            base_dir=tmp_path,
        )


def test_auth_plugin_resolution(tmp_path: Path) -> None:
    plugin = _AuthPlugin()
    material = resolve_auth_material(
        {"type": "plugin", "provider": "custom_auth"},
        base_dir=tmp_path,
        auth_plugins=[plugin],
    )
    assert material.headers["Authorization"].startswith("Custom")


def test_auth_invalid_raises(tmp_path: Path) -> None:
    with pytest.raises(AuthResolutionError):
        resolve_auth_material({"type": "basic", "username": "u"}, base_dir=tmp_path)


def test_redaction_masks_sensitive_keys_and_patterns() -> None:
    payload = {
        "token": "abc",
        "headers": {"Authorization": "Bearer abc", "X-Test": "1"},
        "nested": {"password": "pw"},
    }
    red = redact_payload(payload)
    assert red["token"] == REDACTED
    assert red["headers"]["Authorization"] == REDACTED
    assert red["nested"]["password"] == REDACTED

    assert REDACTED in redact_url("https://user:pass@example.com/solr")
    assert REDACTED in redact_text("Authorization: Bearer abc123")


def test_profile_resolution_defaults() -> None:
    assert resolve_profile("enterprise-safe").redact_artifacts
    assert resolve_profile("summary-only").summary_only
    with pytest.raises(ValueError):
        resolve_profile("missing")


def test_audit_record_shape() -> None:
    record = build_audit_record(
        run_id="r1",
        timestamp="2026-01-01T00:00:00Z",
        profile="enterprise-safe",
        requested_by="alice",
        team="search-platform",
        ticket_id="CR-1",
        environment_label="prod-eu",
        notes="run note",
        baseline_url="http://b",
        baseline_collection="c1",
        shadow_url="http://s",
        shadow_collection="c2",
        baseline_auth_mode="basic",
        shadow_auth_mode="bearer",
        plugins=["custom_auth"],
    )
    assert record["run_id"] == "r1"
    assert record["targets"]["baseline"]["auth_mode"] == "basic"
    assert record["ticket_id"] == "CR-1"
