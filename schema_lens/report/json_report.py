"""Build final JSON report payload."""

from __future__ import annotations

from typing import Any


def build_report_json(
    *,
    manifest: dict[str, Any],
    compare_data: dict[str, Any],
    replay_data: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "queries_total": compare_data.get("summary", {}).get("queries_total", 0),
        "failures": replay_data.get("stats", {}).get("failures", 0),
        "avg_overlap": compare_data.get("summary", {}).get("avg_overlap", 0),
        "high_risk_percent": compare_data.get("summary", {}).get("high_risk_percent", 0),
        "avg_numfound_delta": compare_data.get("summary", {}).get("avg_numfound_delta", 0),
        "avg_sort_instability_ratio": compare_data.get("summary", {}).get(
            "avg_sort_instability_ratio", 0
        ),
        "queries_with_facet_changes_percent": compare_data.get("summary", {}).get(
            "queries_with_facet_changes_percent", 0
        ),
    }

    top_regressions = []
    for diff in compare_data.get("top_regressions", []):
        facet_marker = None
        facet_diffs = diff.get("facet_diffs", {})
        if isinstance(facet_diffs, dict):
            for field, section in facet_diffs.items():
                if not isinstance(section, dict):
                    continue
                deltas = section.get("top_deltas", [])
                if deltas:
                    top = deltas[0]
                    facet_marker = {
                        "field": field,
                        "value": top.get("value"),
                        "delta": top.get("delta"),
                    }
                    break
        top_regressions.append(
            {
                "query_id": diff.get("query_id"),
                "raw_q": diff.get("raw_line"),
                "risk": diff.get("risk_severity"),
                "overlap": diff.get("topk_overlap_count"),
                "jaccard": diff.get("jaccard"),
                "kendall_tau": diff.get("kendall_tau"),
                "numfound_delta": diff.get("numfound_delta"),
                "sort_instability_ratio": diff.get("sort_instability_ratio"),
                "biggest_facet_delta": facet_marker,
                "dropped_top_doc": (
                    diff.get("dropped_docs", [None])[0]
                    if diff.get("dropped_docs")
                    else None
                ),
            }
        )

    return {
        "run_manifest": manifest,
        "summary": summary,
        "schema_safety_findings": compare_data.get("schema_safety_findings", {}),
        "query_rewrite_impact": compare_data.get("rewrite_diff", {}),
        "top_regressions": top_regressions,
        "per_query_diffs": compare_data.get("diffs", []),
        "explain_bundles": compare_data.get("explain_bundles", []),
    }
