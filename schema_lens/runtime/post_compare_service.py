from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from schema_lens.changesets.apply_queryparams import merge_queryparams
from schema_lens.compare.explain_fetcher import fetch_explains
from schema_lens.compare.rewrite_diff import load_synonym_rules_from_changes, run_rewrite_diff
from schema_lens.compat.adapters import metrics_supported, structured_explain_supported
from schema_lens.perf.analyzer import analyze_performance
from schema_lens.perf.solr_metrics import collect_solr_runtime_snapshot
from schema_lens.segments import build_segment_report
from schema_lens.util.io import write_json
from schema_lens.vector.compare import compare_vector_hybrid
from schema_lens.vector.replay import run_vector_scenarios
from schema_lens.vector.sensitivity import run_hybrid_sensitivity


def build_segment_payload(*, changeset_raw: dict[str, Any], compare_data: dict[str, Any]) -> dict[str, Any]:
    segments_cfg = changeset_raw.get("segments", {})
    if not isinstance(segments_cfg, dict):
        segments_cfg = {}
    enabled = bool(segments_cfg.get("enabled", True))
    if not enabled:
        return {"enabled": False, "reason": "Segment analysis disabled."}

    segment_keys = (
        [str(item) for item in segments_cfg.get("keys", []) if isinstance(item, str)]
        if isinstance(segments_cfg.get("keys"), list)
        else None
    )
    segment_policy = segments_cfg.get("policy", {}) if isinstance(segments_cfg.get("policy"), dict) else {}
    return build_segment_report(
        compare_data=compare_data,
        policy=segment_policy,
        segment_keys=segment_keys,
    )


def run_vector_flow(
    *,
    vector_runtime_cfg,
    shadow_name: str | None,
    baseline_client,
    baseline_collection: str,
    shadow_client,
    query_cases,
    baseline_request_defaults: dict[str, Any],
    changes: list[Any],
    effective_k: int,
    replay_data: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    if not vector_runtime_cfg.enabled:
        return {
            "vector_replay_data": {"enabled": False, "scenario_results": {}},
            "replay_scenarios": {},
            "vector_hybrid": {"enabled": False},
            "hybrid_sensitivity": {"enabled": False, "weights": [], "scenarios": []},
        }

    if not shadow_name:
        raise ValueError("Shadow name unavailable during scenario_replay stage")

    merged_defaults = merge_queryparams(baseline_request_defaults, changes)
    vector_replay_data = run_vector_scenarios(
        baseline_client=baseline_client,
        baseline_collection=baseline_collection,
        shadow_client=shadow_client,
        shadow_collection=shadow_name,
        queries=query_cases,
        request_defaults=merged_defaults,
        vector_cfg=vector_runtime_cfg,
    )
    replay_data["vector_scenarios"] = vector_replay_data

    per_scenario_paths: dict[str, str] = {}
    scenario_results = vector_replay_data.get("scenario_results", {})
    if isinstance(scenario_results, dict):
        for scenario_name, payload in scenario_results.items():
            safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in scenario_name)
            scenario_path = out_dir / f"replay_{safe}.json"
            write_json(scenario_path, payload)
            per_scenario_paths[scenario_name] = str(scenario_path.resolve())

    vector_compare = compare_vector_hybrid(
        scenario_replay=vector_replay_data,
        top_k=int(vector_runtime_cfg.evaluation.get("topK", effective_k)),
    )

    sensitivity_cfg = (
        vector_runtime_cfg.evaluation.get("sensitivity", {})
        if isinstance(vector_runtime_cfg.evaluation, dict)
        else {}
    )
    if bool(sensitivity_cfg.get("enabled", False)):
        hybrid_sensitivity_data = run_hybrid_sensitivity(
            scenario_replay=vector_replay_data,
            weights=[float(w) for w in sensitivity_cfg.get("weights", [])],
            top_k=int(vector_runtime_cfg.evaluation.get("topK", effective_k)),
            candidate_pool=int(vector_runtime_cfg.evaluation.get("candidate_pool", max(100, effective_k))),
        )
    else:
        hybrid_sensitivity_data = {"enabled": False, "weights": [], "scenarios": []}

    return {
        "vector_replay_data": vector_replay_data,
        "replay_scenarios": per_scenario_paths,
        "vector_hybrid": vector_compare,
        "hybrid_sensitivity": hybrid_sensitivity_data,
    }


def run_rewrite_diff_flow(
    *,
    eval_cfg: dict[str, Any],
    changes: list[Any],
    changeset_path: Path,
    baseline_client,
    baseline_collection: str,
    shadow_client,
    shadow_name: str | None,
    replay_data: dict[str, Any],
    compare_data: dict[str, Any],
    effective_k: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rewrite_cfg = eval_cfg.get("rewrite_diff", {})
    settings = rewrite_cfg if isinstance(rewrite_cfg, dict) else {}

    if not (isinstance(rewrite_cfg, dict) and rewrite_cfg.get("enabled", False)):
        return {
            "enabled": False,
            "per_query": [],
            "top_clause_deltas": [],
            "top_synonym_changed": [],
        }, settings

    if not shadow_name:
        raise ValueError("Shadow name unavailable during rewrite_diff stage")

    synonym_rules = load_synonym_rules_from_changes(
        changes,
        changeset_path=str(changeset_path.resolve()),
    )
    has_synonym_changes = any(
        op.get("op") == "schema.synonym.update" for op in changes if isinstance(op, dict)
    )
    rewrite_data = run_rewrite_diff(
        baseline_client=baseline_client,
        baseline_collection=baseline_collection,
        shadow_client=shadow_client,
        shadow_collection=shadow_name,
        replay_pairs=replay_data.get("pairs", []),
        diffs=compare_data.get("diffs", []),
        k=effective_k,
        rewrite_cfg=rewrite_cfg,
        synonym_rules=synonym_rules,
        has_synonym_changes=has_synonym_changes,
    )

    rewrite_flags_by_qid = {
        item.get("query_id"): item.get("risk_flags", [])
        for item in rewrite_data.get("per_query", [])
        if item.get("query_id") is not None
    }
    for diff_row in compare_data.get("diffs", []):
        qid = diff_row.get("query_id")
        flags = rewrite_flags_by_qid.get(qid, [])
        if not isinstance(diff_row.get("risk_flags"), list):
            diff_row["risk_flags"] = []
        for flag in flags:
            if flag not in diff_row["risk_flags"]:
                diff_row["risk_flags"].append(flag)
    for diff_row in compare_data.get("top_regressions", []):
        qid = diff_row.get("query_id")
        flags = rewrite_flags_by_qid.get(qid, [])
        if not isinstance(diff_row.get("risk_flags"), list):
            diff_row["risk_flags"] = []
        for flag in flags:
            if flag not in diff_row["risk_flags"]:
                diff_row["risk_flags"].append(flag)

    return rewrite_data, settings


def run_explain_flow(
    *,
    eval_cfg: dict[str, Any],
    compat_caps: dict[str, Any],
    baseline_client,
    baseline_collection: str,
    shadow_client,
    shadow_name: str | None,
    replay_data: dict[str, Any],
    compare_data: dict[str, Any],
    effective_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    explain_cfg = eval_cfg.get("explain", {})
    if not (isinstance(explain_cfg, dict) and explain_cfg.get("enabled", False)):
        return [], None

    requested_structured = bool(explain_cfg.get("structured", False))
    effective_structured = requested_structured and structured_explain_supported(compat_caps)
    fallback = None
    if requested_structured and not effective_structured:
        fallback = {
            "feature": "structured_explain",
            "reason": "structured_explain_supported capability is unavailable",
        }

    bundles = fetch_explains(
        baseline_client=baseline_client,
        baseline_collection=baseline_collection,
        shadow_client=shadow_client,
        shadow_collection=shadow_name,
        replay_pairs=replay_data.get("pairs", []),
        diffs=compare_data.get("diffs", []),
        k=effective_k,
        max_queries=int(explain_cfg.get("max_queries", 25)),
        max_docs_per_query=int(explain_cfg.get("max_docs_per_query", 3)),
        structured=effective_structured,
    )
    return bundles, fallback


def run_performance_analyze_flow(
    *,
    changeset_raw: dict[str, Any],
    compat_caps: dict[str, Any],
    baseline_client,
    baseline_collection: str,
    shadow_client,
    shadow_name: str | None,
    replay_data: dict[str, Any],
    compare_data: dict[str, Any],
    changes: list[Any],
    perf_before: dict[str, Any],
    disabled_section: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    perf_cfg = changeset_raw.get("performance", {})
    if isinstance(perf_cfg, dict) and perf_cfg.get("enabled", False) and metrics_supported(compat_caps):
        cache_cfg = perf_cfg.get("caches", {})
        cache_names = (
            cache_cfg.get("names")
            if isinstance(cache_cfg, dict) and isinstance(cache_cfg.get("names"), list)
            else None
        )
        perf_after = {
            "baseline": collect_solr_runtime_snapshot(
                client=baseline_client,
                collection=baseline_collection,
                cache_names=cache_names,
                include_luke=bool(
                    (perf_cfg.get("index", {}) or {}).get("luke", True)
                    if isinstance(perf_cfg.get("index"), dict)
                    else True
                ),
            ),
            "shadow": collect_solr_runtime_snapshot(
                client=shadow_client,
                collection=shadow_name or "",
                cache_names=cache_names,
                include_luke=bool(
                    (perf_cfg.get("index", {}) or {}).get("luke", True)
                    if isinstance(perf_cfg.get("index"), dict)
                    else True
                ),
            ),
        }
        percentiles_capture = perf_cfg.get("capture")
        percentiles_cfg = percentiles_capture if isinstance(percentiles_capture, dict) else {}
        percentiles = (
            percentiles_cfg.get("percentiles")
            if isinstance(percentiles_cfg.get("percentiles"), list)
            else [50, 95, 99]
        )
        perf_metrics_data = analyze_performance(
            replay_data=replay_data,
            compare_data=compare_data,
            baseline_snapshot=perf_after["baseline"],
            shadow_snapshot=perf_after["shadow"],
            changes=changes,
            percentiles=[int(item) for item in percentiles],
        )
        perf_metrics_data["before"] = perf_before
        perf_metrics_data["after"] = perf_after
        return perf_metrics_data

    if isinstance(perf_cfg, dict) and perf_cfg.get("enabled", False):
        return disabled_section("Performance capture not available for detected Solr capabilities.")
    return disabled_section("Performance capture not enabled.")
