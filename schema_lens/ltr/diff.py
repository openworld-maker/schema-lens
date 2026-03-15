"""LTR feature diff helpers."""

from __future__ import annotations

from typing import Any


def parse_feature_string(value: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for chunk in value.split(","):
        part = chunk.strip()
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        try:
            out[key.strip()] = float(raw.strip())
        except ValueError:
            continue
    return out


def diff_feature_maps(
    baseline: dict[str, float],
    shadow: dict[str, float],
) -> list[dict[str, Any]]:
    keys = sorted(set(baseline.keys()) | set(shadow.keys()))
    rows: list[dict[str, Any]] = []
    for key in keys:
        base = baseline.get(key, 0.0)
        sh = shadow.get(key, 0.0)
        if base == sh:
            continue
        rows.append({"feature": key, "baseline": base, "shadow": sh, "delta": sh - base})
    rows.sort(key=lambda row: abs(float(row["delta"])), reverse=True)
    return rows
