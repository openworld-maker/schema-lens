"""Auth provider plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class AuthProviderPlugin(BasePlugin):
    """Provide request auth material for external systems."""

    def build_auth(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}
