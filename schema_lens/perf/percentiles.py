"""Percentile helpers."""

from __future__ import annotations


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    index = (len(ordered) - 1) * (pct / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    weight = index - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def summarize_percentiles(values: list[float], percentiles: list[int]) -> dict[str, float]:
    return {f"p{pct}": percentile(values, int(pct)) for pct in percentiles}
