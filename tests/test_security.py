from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.plugins.contracts.auth import AuthProviderPlugin
from schema_lens.security.audit import build_audit_record
from schema_lens.security.auth import AuthResolutionError, resolve_auth_material
from schema_lens.security.profiles import resolve_profile
from schema_lens.security.redaction import redact_payload
from schema_lens.security.secrets import resolve_secret_field


class _AuthPlugin(AuthProviderPlugin):
    metadata = type(
        "Meta",
        (),
        {
            "name": "kerb_plugin",
            "version": "0.1.0",
            "plugin_type": "auth",
            "capabilities": ["kerberos"],
            "schema_lens_version": "*",
        },
    )()

    def build_auth(self, context):
        return {"headers": {"Authorization": "Negotiate abc"}}


def test_resolve_secret_field_env_and_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_USER", "alice")
    f = tmp_path / "pw.txt"
    f.write_text("s3cr3t\n", encoding="utf-8")

    cfg = {"username_env": "SEC_USER", "password_file": str(f)}
    assert resolve_secret_field(cfg, "username", base_dir=tmp_path) == "alice"
    assert resolve_secret_field(cfg, "password", base_dir=tmp_path) == "s3cr3t"


def test_auth_basic_and_bearer_resolution(tmp_path: Path) -> None:
    basic = resolve_auth_material(
        {"type": "basic", "username": "u", "password": "p"},
        base_dir=tmp_path,
    )
    assert basic.mode == "basic"
    assert basic.headers["Authorization"].startswith("Basic ")

    bearer = resolve_auth_material(
        {"type": "bearer", "token": "abc"},
        base_dir=tmp_path,
    )
    assert bearer.headers["Authorization"] == "Bearer abc"


def test_auth_mtls_resolution(tmp_path: Path) -> None:
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


def test_auth_plugin_resolution(tmp_path: Path) -> None:
    plugin = _AuthPlugin()
    material = resolve_auth_material(
        {"type": "plugin", "provider": "kerb_plugin"},
        base_dir=tmp_path,
        auth_plugins=[plugin],
    )
    assert material.headers["Authorization"].startswith("Negotiate")


def test_auth_invalid_raises(tmp_path: Path) -> None:
    with pytest.raises(AuthResolutionError):
        resolve_auth_material({"type": "basic", "username": "u"}, base_dir=tmp_path)


def test_redaction_masks_sensitive_keys() -> None:
    payload = {
        "token": "abc",
        "headers": {"Authorization": "Bearer abc", "X-Test": "1"},
        "nested": {"password": "pw"},
    }
    red = redact_payload(payload)
    assert red["token"] == "<redacted>"
    assert red["headers"]["Authorization"] == "<redacted>"
    assert red["nested"]["password"] == "<redacted>"


def test_profile_resolution_defaults() -> None:
    assert resolve_profile("enterprise-safe").redact_artifacts
    assert resolve_profile("missing").name == "local-dev"


def test_audit_record_shape() -> None:
    record = build_audit_record(
        run_id="r1",
        timestamp="2026-01-01T00:00:00Z",
        profile="enterprise-safe",
        requested_by="alice",
        approval_reference="CR-1",
        baseline_url="http://b",
        baseline_collection="c1",
        shadow_url="http://s",
        shadow_collection="c2",
        baseline_auth_mode="basic",
        shadow_auth_mode="bearer",
    )
    assert record["run_id"] == "r1"
    assert record["targets"]["baseline"]["auth_mode"] == "basic"
