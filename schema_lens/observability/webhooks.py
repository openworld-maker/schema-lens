"""Webhook event sink for run lifecycle notifications."""

from __future__ import annotations

from typing import Any

import httpx


class WebhookEmitter:
    def __init__(
        self,
        *,
        enabled: bool,
        urls: list[str],
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.enabled = enabled
        self.urls = urls
        self.headers = headers or {}
        self.timeout_seconds = timeout_seconds

    def emit(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.enabled or not self.urls:
            return []
        deliveries: list[dict[str, Any]] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for url in self.urls:
                try:
                    response = client.post(url, json=event, headers=self.headers)
                    deliveries.append(
                        {
                            "url": url,
                            "ok": response.status_code < 400,
                            "status_code": response.status_code,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    deliveries.append({"url": url, "ok": False, "error": str(exc)})
        return deliveries
