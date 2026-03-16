"""Auth provider plugin contract."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class AuthProviderPlugin(BasePlugin):
    """Provide request auth material for external systems."""

    def validate_config(self, config: dict[str, Any]) -> None:
        return None

    def build_auth(self, context: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible auth hook."""
        return {}

    def build_request_auth(self, config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return self.build_auth(context)

    def redact(self, config: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in config.items():
            key_lower = key.lower()
            if any(token in key_lower for token in ("token", "password", "secret", "key")):
                safe[key] = "<redacted>"
            else:
                safe[key] = value
        return safe
