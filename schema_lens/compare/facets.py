"""Facet diff helpers."""

from __future__ import annotations

from typing import Any


def parse_facet_fields(raw: Any) -> dict[str, int]:
    if isinstance(raw, dict):
        out: dict[str, int] = {}
        for key, value in raw.items():
            try:
                out[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(raw, list):
        out = {}
        for i in range(0, len(raw), 2):
            if i + 1 >= len(raw):
                break
            key = raw[i]
            val = raw[i + 1]
            if key is None:
                continue
            try:
                out[str(key)] = int(val)
            except (TypeError, ValueError):
                continue
        return out
    return {}


def compute_facet_diff(
    baseline: dict[str, dict[str, int]],
    shadow: dict[str, dict[str, int]],
    *,
    top_n: int = 20,
) -> dict[str, Any]:
    fields = sorted(set(baseline.keys()) | set(shadow.keys()))
    result: dict[str, Any] = {}
    for field in fields:
        base_counts = baseline.get(field, {})
        shadow_counts = shadow.get(field, {})
        values = set(base_counts.keys()) | set(shadow_counts.keys())

        new_values = sorted([v for v in values if v not in base_counts])
        missing_values = sorted([v for v in values if v not in shadow_counts])

        deltas: list[dict[str, Any]] = []
        for value in values:
            b = int(base_counts.get(value, 0))
            s = int(shadow_counts.get(value, 0))
            if b == s:
                continue
            deltas.append(
                {
                    "value": value,
                    "baseline": b,
                    "shadow": s,
                    "delta": s - b,
                }
            )
        deltas.sort(key=lambda d: abs(int(d["delta"])), reverse=True)
        result[field] = {
            "new_values": new_values,
            "missing_values": missing_values,
            "top_deltas": deltas[:top_n],
        }
    return result

