"""Formatting helpers for recommendations."""

from __future__ import annotations

from typing import Any


def summarize_recommendation(row: dict[str, Any]) -> str:
    return f"{row.get('recommendation_code')}: {row.get('rationale')}"
