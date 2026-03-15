"""Formatting helpers for root cause findings."""

from __future__ import annotations

from typing import Any


def summarize_finding(finding: dict[str, Any]) -> str:
    evidence = finding.get("evidence", [])
    reason = evidence[0] if evidence else "Evidence recorded in artifact."
    return f"{finding.get('cause_code')}: {reason}"
