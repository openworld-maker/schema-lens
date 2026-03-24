"""No-op auth provider."""

from __future__ import annotations

from schema_lens.security.auth_models import AuthMaterial


def build_none_auth() -> AuthMaterial:
    return AuthMaterial(mode="none")
