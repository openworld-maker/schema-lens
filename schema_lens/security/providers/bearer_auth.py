"""Bearer auth provider."""

from __future__ import annotations

from schema_lens.security.auth_models import AuthMaterial


def build_bearer_auth(token: str) -> AuthMaterial:
    return AuthMaterial(mode="bearer", headers={"Authorization": f"Bearer {token}"})
