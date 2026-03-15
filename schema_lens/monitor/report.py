"""Monitoring summary formatting."""

from __future__ import annotations

from typing import Any


def summarize_monitor(latest: dict[str, Any]) -> list[str]:
    drift = latest.get("drift", {}) if isinstance(latest, dict) else {}
    lines: list[str] = []
    for key, value in drift.items():
        if not isinstance(value, dict):
            continue
        lines.append(f"{key}: {float(value.get('delta', 0.0)):+.3f}")
    return lines
