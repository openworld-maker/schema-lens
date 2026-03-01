"""numFound comparison helpers."""

from __future__ import annotations

from typing import Any


def numfound_delta(
    baseline_meta: dict[str, Any],
    shadow_meta: dict[str, Any],
) -> tuple[int | None, int | None, int | None]:
    base_raw = baseline_meta.get("numFound")
    shadow_raw = shadow_meta.get("numFound")
    try:
        base = int(base_raw) if base_raw is not None else None
    except (TypeError, ValueError):
        base = None
    try:
        shd = int(shadow_raw) if shadow_raw is not None else None
    except (TypeError, ValueError):
        shd = None
    delta = shd - base if base is not None and shd is not None else None
    return base, shd, delta

