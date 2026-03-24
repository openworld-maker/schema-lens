"""Basic auth provider."""

from __future__ import annotations

import base64

from schema_lens.security.auth_models import AuthMaterial


def build_basic_auth(username: str, password: str) -> AuthMaterial:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return AuthMaterial(mode="basic", headers={"Authorization": f"Basic {token}"})
