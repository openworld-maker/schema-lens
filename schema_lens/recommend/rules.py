"""Recommendation rules keyed by root cause."""

from __future__ import annotations

from schema_lens.recommend.model import Recommendation


def recommendations_for_cause(cause_code: str) -> list[Recommendation]:
    mapping = {
        "PREFIX_MATCHING_REMOVED": [
            Recommendation(
                recommendation_code="USE_DUAL_FIELD_PREFIX_STRATEGY",
                rationale=(
                    "Keep prefix matching on a dedicated field instead of removing it "
                    "from the main field."
                ),
                safety_level="moderate",
                implementation_steps=[
                    "Add a prefix-oriented field type and field.",
                    "Populate via copyField from the main text field.",
                    "Blend that field into qf for head/prefix queries only.",
                ],
                rollback_hint="Restore the previous analyzer chain on the original field.",
                confidence="HIGH",
            )
        ],
        "ANALYSIS_REMOVED_OR_FIELD_EXACTIFIED": [
            Recommendation(
                recommendation_code="USE_COPYFIELD_MIGRATION_PATH",
                rationale=(
                    "Changing a searchable text field to exact matching is safer via "
                    "side-by-side fields."
                ),
                safety_level="high_touch",
                implementation_steps=[
                    "Add a new exact field instead of replacing the analyzed field.",
                    "Backfill with copyField or reindex.",
                    "Shift queries gradually and validate golden queries.",
                ],
                rollback_hint="Keep existing analyzed field in query path until parity is proven.",
                confidence="HIGH",
            )
        ],
        "TITLE_BOOST_REDUCED": [
            Recommendation(
                recommendation_code="REDUCE_BOOST_STEP_SIZE",
                rationale="Large qf/pf swings create unstable ranking for head queries.",
                safety_level="low_risk",
                implementation_steps=[
                    "Test smaller boost steps.",
                    "Compare two or three intermediate qf/pf settings.",
                    "Keep expected head documents pinned via golden queries.",
                ],
                rollback_hint="Restore prior qf/pf weights.",
                confidence="MEDIUM",
            )
        ],
        "MIN_SHOULD_MATCH_STRICTER": [
            Recommendation(
                recommendation_code="RELAX_MM_STEPWISE",
                rationale="A stricter mm often cuts recall too sharply for long queries.",
                safety_level="low_risk",
                implementation_steps=[
                    "Back off mm one step.",
                    "Retain stricter behavior only for head queries if needed.",
                ],
                rollback_hint="Restore previous mm setting.",
                confidence="MEDIUM",
            )
        ],
        "VECTOR_DOMINANCE_INCREASED": [
            Recommendation(
                recommendation_code="RUN_HYBRID_WEIGHT_SWEEP",
                rationale="The hybrid blend shifted too far toward vector ranking.",
                safety_level="low_risk",
                implementation_steps=[
                    "Run 0.7/0.3, 0.6/0.4, and 0.5/0.5 sweeps.",
                    "Protect exact part-number queries with lexical guardrails.",
                ],
                rollback_hint="Restore prior lexical/vector blend weights.",
                confidence="HIGH",
            )
        ],
        "CACHE_OR_LATENCY_REGRESSION": [
            Recommendation(
                recommendation_code="REDUCE_CACHE_PRESSURE_OR_DOCVALUES_HOTPATH",
                rationale="The change increases latency or cache churn under load.",
                safety_level="moderate",
                implementation_steps=[
                    "Reduce facet breadth or rows for heavy queries.",
                    "Add docValues only where sort/facet paths are hot.",
                    "Trim stored fields in performance-sensitive flows.",
                ],
                rollback_hint="Restore prior schema/query defaults while perf is re-evaluated.",
                confidence="MEDIUM",
            )
        ],
    }
    return mapping.get(cause_code, [])
