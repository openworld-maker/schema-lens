"""Interval parsing helpers."""

from __future__ import annotations


def normalize_interval(raw: str) -> str:
    text = raw.strip().lower()
    return text or "24h"
