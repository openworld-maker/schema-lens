"""Sampling utilities for extracted query parameter sets."""

from __future__ import annotations

import json
import random
from typing import Any


def _fingerprint(params: dict[str, Any]) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def sample_top(
    rows: list[dict[str, Any]],
    *,
    max_queries: int | None = None,
) -> list[dict[str, Any]]:
    if max_queries is None or max_queries <= 0:
        return list(rows)

    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    payload: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows):
        params = row.get("params", {})
        if not isinstance(params, dict):
            continue
        key = _fingerprint(params)
        counts[key] = counts.get(key, 0) + 1
        first_seen.setdefault(key, idx)
        payload.setdefault(key, row)

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], first_seen[item[0]]),
    )
    selected_keys = [key for key, _ in ranked[:max_queries]]
    return [payload[key] for key in selected_keys]


def sample_reservoir(
    rows: list[dict[str, Any]],
    *,
    max_queries: int | None = None,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    if max_queries is None or max_queries <= 0:
        return list(rows)

    rng = random.Random(seed)
    reservoir: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        if i < max_queries:
            reservoir.append(row)
            continue
        j = rng.randint(0, i)
        if j < max_queries:
            reservoir[j] = row

    return reservoir


def sample_queries(
    rows: list[dict[str, Any]],
    *,
    mode: str = "reservoir",
    max_queries: int | None = None,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    if mode == "top":
        return sample_top(rows, max_queries=max_queries)
    return sample_reservoir(rows, max_queries=max_queries, seed=seed)

