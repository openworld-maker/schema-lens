"""mTLS auth provider."""

from __future__ import annotations

from pathlib import Path

from schema_lens.security.auth_models import AuthMaterial
from schema_lens.security.errors import AuthProviderError


def build_mtls_auth(
    *,
    cert_file: str,
    key_file: str | None,
    ca_file: str | None,
    base_dir: Path,
    verify: bool | str = True,
) -> AuthMaterial:
    cert_path = Path(cert_file)
    if not cert_path.is_absolute():
        cert_path = (base_dir / cert_path).resolve()
    if not cert_path.exists():
        raise AuthProviderError("mTLS cert_file does not exist")

    cert: str | tuple[str, str]
    if key_file:
        key_path = Path(key_file)
        if not key_path.is_absolute():
            key_path = (base_dir / key_path).resolve()
        if not key_path.exists():
            raise AuthProviderError("mTLS key_file does not exist")
        cert = (str(cert_path), str(key_path))
    else:
        cert = str(cert_path)

    verify_value: bool | str
    if ca_file:
        ca_path = Path(ca_file)
        if not ca_path.is_absolute():
            ca_path = (base_dir / ca_path).resolve()
        if not ca_path.exists():
            raise AuthProviderError("mTLS ca_file does not exist")
        verify_value = str(ca_path)
    else:
        verify_value = verify

    return AuthMaterial(mode="mtls", cert=cert, verify=verify_value)
