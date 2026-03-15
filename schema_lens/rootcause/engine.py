"""Root cause analysis engine."""

from __future__ import annotations

from typing import Any

from schema_lens.rootcause.model import RootCauseFinding
from schema_lens.rootcause.rules import (
    analysis_removed_or_field_exactified,
    cache_or_latency_regression,
    facet_field_behavior_changed,
    min_should_match_stricter,
    prefix_matching_removed,
    title_boost_reduced,
    vector_dominance_increased,
)
from schema_lens.rootcause.templates import summarize_finding


def _append_unique(rows: list[RootCauseFinding], finding: RootCauseFinding | None) -> None:
    if finding is None:
        return
    if any(existing.cause_code == finding.cause_code for existing in rows):
        return
    rows.append(finding)


def analyze_root_causes(
    *,
    compare_data: dict[str, Any],
    changes: list[dict[str, Any]],
    baseline_request_defaults: dict[str, Any],
) -> dict[str, Any]:
    rewrite_per_query = {
        row.get("query_id"): row
        for row in compare_data.get("rewrite_diff", {}).get("per_query", [])
        if isinstance(row, dict) and row.get("query_id") is not None
    }
    findings: list[RootCauseFinding] = []

    _append_unique(
        findings,
        prefix_matching_removed(changes=changes, rewrite_row=None),
    )
    _append_unique(
        findings,
        title_boost_reduced(
            baseline_defaults=baseline_request_defaults,
            changes=changes,
        ),
    )
    _append_unique(
        findings,
        analysis_removed_or_field_exactified(changes=changes),
    )
    _append_unique(
        findings,
        vector_dominance_increased(vector_hybrid=compare_data.get("vector_hybrid", {})),
    )
    _append_unique(
        findings,
        cache_or_latency_regression(performance=compare_data.get("performance", {})),
    )

    per_query: list[dict[str, Any]] = []
    for diff_row in compare_data.get("top_regressions", []):
        if not isinstance(diff_row, dict):
            continue
        query_findings: list[RootCauseFinding] = []
        query_id = diff_row.get("query_id")
        _append_unique(
            query_findings,
            min_should_match_stricter(
                baseline_defaults=baseline_request_defaults,
                changes=changes,
                diff_row=diff_row,
            ),
        )
        _append_unique(
            query_findings,
            facet_field_behavior_changed(diff_row=diff_row),
        )
        _append_unique(
            query_findings,
            prefix_matching_removed(
                changes=changes,
                rewrite_row=rewrite_per_query.get(query_id),
            ),
        )
        if query_findings:
            per_query.append(
                {
                    "query_id": query_id,
                    "causes": [finding.to_dict() for finding in query_findings],
                }
            )

    overall = [finding.to_dict() for finding in findings]
    return {
        "enabled": True,
        "overall": overall,
        "per_query": per_query,
        "summaries": [summarize_finding(row) for row in overall],
    }
