"""Retry helpers for HTTP requests."""

from __future__ import annotations

from collections.abc import Iterable

RETRYABLE_STATUS_CODES = {429, 503, 504}
RETRY_DELAYS_SECONDS = [0.5, 1.0, 2.0, 4.0]


def retry_delays() -> Iterable[float]:
    return RETRY_DELAYS_SECONDS
