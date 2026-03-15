"""Promotion state validation and transitions."""

from __future__ import annotations

PROMOTION_STATES = ["dev", "stage", "prod_candidate", "prod_approved"]

_ALLOWED = {
    "dev": {"stage"},
    "stage": {"prod_candidate", "dev"},
    "prod_candidate": {"prod_approved", "stage"},
    "prod_approved": set(),
}


def validate_promotion_state(state: str) -> str:
    value = str(state).strip()
    if value not in PROMOTION_STATES:
        raise ValueError(f"invalid promotion state: {value}")
    return value


def validate_transition(current: str, target: str) -> None:
    src = validate_promotion_state(current)
    dst = validate_promotion_state(target)
    if dst not in _ALLOWED[src]:
        raise ValueError(f"invalid promotion transition: {src} -> {dst}")
