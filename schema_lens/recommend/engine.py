"""Recommendation engine."""

from __future__ import annotations

from typing import Any

from schema_lens.recommend.rules import recommendations_for_cause
from schema_lens.recommend.templates import summarize_recommendation


def build_recommendations(root_causes: dict[str, Any]) -> dict[str, Any]:
    overall: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in root_causes.get("overall", []):
        cause_code = finding.get("cause_code")
        if not isinstance(cause_code, str):
            continue
        for recommendation in recommendations_for_cause(cause_code):
            payload = recommendation.to_dict()
            if payload["recommendation_code"] in seen:
                continue
            seen.add(str(payload["recommendation_code"]))
            payload["source_cause_code"] = cause_code
            overall.append(payload)

    per_cause: dict[str, Any] = {}
    for finding in root_causes.get("overall", []):
        cause_code = finding.get("cause_code")
        if not isinstance(cause_code, str):
            continue
        per_cause[cause_code] = [
            recommendation.to_dict() for recommendation in recommendations_for_cause(cause_code)
        ]

    return {
        "enabled": True,
        "overall": overall,
        "per_cause": per_cause,
        "summaries": [summarize_recommendation(row) for row in overall],
    }
