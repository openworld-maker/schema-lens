"""Apply queryparam change operations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def merge_queryparams(
    base_defaults: dict[str, Any],
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    merged = deepcopy(base_defaults)
    for op in changes:
        if op.get("op") == "queryparams.set":
            updates = op.get("set", {})
            if isinstance(updates, dict):
                merged.update(updates)
    return merged
