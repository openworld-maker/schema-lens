"""Timing helpers for replay and perf analysis."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any


def timed_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    started = perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (perf_counter() - started) * 1000.0
    return result, round(elapsed_ms, 3)
