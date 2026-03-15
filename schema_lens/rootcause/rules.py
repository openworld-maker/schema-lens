"""Deterministic diagnosis rules."""

from __future__ import annotations

from typing import Any

from schema_lens.rootcause.model import RootCauseFinding


def prefix_matching_removed(
    *,
    changes: list[dict[str, Any]],
    rewrite_row: dict[str, Any] | None,
) -> RootCauseFinding | None:
    for op in changes:
        if not isinstance(op, dict):
            continue
        if op.get("op") == "schema.analyzer.remove_filter" and "NGram" in str(
            op.get("filter_class", "")
        ):
            evidence = ["Analyzer removed prefix/ngram filter."]
            if rewrite_row and "PARSED_QUERY_SHAPE_CHANGED" in rewrite_row.get("risk_flags", []):
                evidence.append("Rewrite diff changed parsed query shape.")
            return RootCauseFinding(
                cause_code="PREFIX_MATCHING_REMOVED",
                confidence="HIGH",
                evidence=evidence,
                affected_query_classes=["lexical"],
            )
    return None


def title_boost_reduced(
    *,
    baseline_defaults: dict[str, Any],
    changes: list[dict[str, Any]],
) -> RootCauseFinding | None:
    base_qf = str((baseline_defaults.get("extra_params", {}) or {}).get("qf", ""))
    for op in changes:
        if not isinstance(op, dict) or op.get("op") != "queryparams.set":
            continue
        updates = op.get("set", {})
        if not isinstance(updates, dict):
            continue
        qf = str(updates.get("qf", ""))
        if "title^" in base_qf and "title^" in qf and qf != base_qf:
            return RootCauseFinding(
                cause_code="TITLE_BOOST_REDUCED",
                confidence="MEDIUM",
                evidence=[f"Query fields changed from `{base_qf}` to `{qf}`."],
                affected_query_classes=["lexical"],
            )
    return None


def min_should_match_stricter(
    *,
    baseline_defaults: dict[str, Any],
    changes: list[dict[str, Any]],
    diff_row: dict[str, Any] | None,
) -> RootCauseFinding | None:
    base_mm = str((baseline_defaults.get("extra_params", {}) or {}).get("mm", ""))
    for op in changes:
        if not isinstance(op, dict) or op.get("op") != "queryparams.set":
            continue
        updates = op.get("set", {})
        if not isinstance(updates, dict) or "mm" not in updates:
            continue
        mm = str(updates.get("mm", ""))
        if mm and mm != base_mm:
            evidence = [f"minShouldMatch changed from `{base_mm}` to `{mm}`."]
            if diff_row and isinstance(diff_row.get("numfound_delta"), (int, float)):
                if float(diff_row["numfound_delta"]) < 0:
                    evidence.append("numFound dropped after the change.")
            return RootCauseFinding(
                cause_code="MIN_SHOULD_MATCH_STRICTER",
                confidence="MEDIUM",
                evidence=evidence,
                affected_query_classes=["lexical"],
            )
    return None


def analysis_removed_or_field_exactified(
    *,
    changes: list[dict[str, Any]],
) -> RootCauseFinding | None:
    for op in changes:
        if not isinstance(op, dict):
            continue
        if op.get("op") == "schema.field.update":
            updates = op.get("set", {})
            if isinstance(updates, dict) and str(updates.get("type", "")).lower() in {
                "string",
                "str",
            }:
                return RootCauseFinding(
                    cause_code="ANALYSIS_REMOVED_OR_FIELD_EXACTIFIED",
                    confidence="HIGH",
                    evidence=[f"Field `{op.get('field')}` moved to exact/string-like type."],
                    affected_query_classes=["lexical", "facet_heavy"],
                )
        if (
            op.get("op") == "schema.fieldType.replace"
            and "string" in str(op.get("with", "")).lower()
        ):
            return RootCauseFinding(
                cause_code="ANALYSIS_REMOVED_OR_FIELD_EXACTIFIED",
                confidence="MEDIUM",
                evidence=[f"Field type replacement targets exact/string type `{op.get('with')}`."],
                affected_query_classes=["lexical", "facet_heavy"],
            )
    return None


def vector_dominance_increased(
    *,
    vector_hybrid: dict[str, Any],
) -> RootCauseFinding | None:
    contributions = vector_hybrid.get("hybrid_contribution", {})
    if not isinstance(contributions, dict):
        return None
    for scenario_name, payload in contributions.items():
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        if float(summary.get("vector_dominant_percent", 0.0)) > 50.0:
            return RootCauseFinding(
                cause_code="VECTOR_DOMINANCE_INCREASED",
                confidence="HIGH",
                evidence=[
                    f"Scenario `{scenario_name}` became vector dominant for most queries."
                ],
                affected_query_classes=["vector", "hybrid"],
            )
    return None


def cache_or_latency_regression(
    *,
    performance: dict[str, Any],
) -> RootCauseFinding | None:
    overall = performance.get("overall", {}) if isinstance(performance, dict) else {}
    base = overall.get("baseline_client_latency_ms", {})
    shadow = overall.get("shadow_client_latency_ms", {})
    base_p95 = float(base.get("p95", 0.0) or 0.0)
    shadow_p95 = float(shadow.get("p95", 0.0) or 0.0)
    if base_p95 and shadow_p95 and shadow_p95 > base_p95 * 1.2:
        return RootCauseFinding(
            cause_code="CACHE_OR_LATENCY_REGRESSION",
            confidence="HIGH",
            evidence=[f"p95 client latency rose from {base_p95:.2f}ms to {shadow_p95:.2f}ms."],
            affected_query_classes=["facet_heavy", "filter_heavy", "sort_heavy"],
        )
    return None


def facet_field_behavior_changed(
    *,
    diff_row: dict[str, Any] | None,
) -> RootCauseFinding | None:
    facet_diffs = diff_row.get("facet_diffs", {}) if isinstance(diff_row, dict) else {}
    if not isinstance(facet_diffs, dict):
        return None
    for field, payload in facet_diffs.items():
        if not isinstance(payload, dict):
            continue
        if payload.get("new_values") or payload.get("missing_values") or payload.get("top_deltas"):
            return RootCauseFinding(
                cause_code="FACET_FIELD_BEHAVIOR_CHANGED",
                confidence="MEDIUM",
                evidence=[f"Facet changes detected for field `{field}`."],
                affected_query_classes=["facet_heavy"],
            )
    return None
