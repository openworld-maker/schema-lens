"""LTR detection heuristics."""

from __future__ import annotations

from typing import Any


def detect_ltr_params(params: dict[str, Any] | None) -> bool:
    params = params if isinstance(params, dict) else {}
    rq = str(params.get("rq", ""))
    fl = str(params.get("fl", ""))
    q = str(params.get("q", ""))
    return (
        "{!ltr" in rq
        or "[features" in fl
        or "{!ltr" in q
        or "reRankQuery" in params
    )
