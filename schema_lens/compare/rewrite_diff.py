"""Query rewrite capture and diff heuristics."""

from __future__ import annotations

import re
from typing import Any

from schema_lens.compare.explain_fetcher import _rank_diffs
from schema_lens.shadow.configset_patcher import load_synonym_rules_from_file
from schema_lens.solr.query_api import select

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def extract_rewrite_info(solr_response: dict[str, Any]) -> dict[str, Any]:
    debug = solr_response.get("debug")
    if not isinstance(debug, dict):
        debug = {}

    parsedquery = _as_text(debug.get("parsedquery") or debug.get("parsedQuery"))
    parsed_to_string = _as_text(
        debug.get("parsedquery_toString")
        or debug.get("parsedQuery_toString")
        or debug.get("parsedquery_to_string")
    )

    if parsed_to_string is None and isinstance(debug.get("QParser"), dict):
        parsed_to_string = _as_text(debug.get("QParser", {}).get("queryString"))

    return {
        "parsedquery": parsedquery,
        "parsedquery_toString": parsed_to_string,
        "debug": debug,
    }


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    out = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in out if token not in {"and", "or", "not"}]


def _clause_count(text: str | None) -> int:
    return len(_tokenize(text))


def _extract_terms(text: str | None) -> set[str]:
    return set(_tokenize(text))


def _contains_term(text: str, term: str) -> bool:
    pattern = re.compile(rf"\b{re.escape(term)}\b")
    return bool(pattern.search(text))


def _synonym_hints(
    *,
    raw_query: str,
    baseline_text: str,
    shadow_text: str,
    synonym_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    query_lower = raw_query.lower()
    base_lower = baseline_text.lower()
    shadow_lower = shadow_text.lower()

    hints: list[dict[str, Any]] = []
    for rule in synonym_rules:
        source = str(rule.get("source", "")).strip().lower()
        targets = [str(target).strip().lower() for target in rule.get("targets", [])]
        targets = [target for target in targets if target]
        if not source or not targets:
            continue

        if not _contains_term(query_lower, source):
            continue

        base_has_target = any(target in base_lower for target in targets)
        shadow_has_target = any(target in shadow_lower for target in targets)
        if base_has_target == shadow_has_target:
            continue

        hints.append(
            {
                "source": source,
                "targets": targets,
                "baseline_has_target": base_has_target,
                "shadow_has_target": shadow_has_target,
            }
        )
        if len(hints) >= 20:
            break

    return hints


def load_synonym_rules_from_changes(
    changes: list[dict[str, Any]],
    *,
    changeset_path: str | None,
) -> list[dict[str, Any]]:
    from pathlib import Path

    rules: list[dict[str, Any]] = []
    for op in changes:
        if op.get("op") != "schema.synonym.update":
            continue

        target = op.get("target", {})
        files = target.get("files", []) if isinstance(target, dict) else []
        if not isinstance(files, list):
            files = []

        source_candidates: list[str] = []
        op_source = op.get("source_file")
        if isinstance(op_source, str) and op_source:
            source_candidates.append(op_source)
        for entry in files:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source_file")
            if isinstance(source, str) and source:
                source_candidates.append(source)

        for raw_source in source_candidates:
            source_path = Path(raw_source)
            if not source_path.is_absolute() and changeset_path:
                source_path = (Path(changeset_path).parent / source_path).resolve()
            elif not source_path.is_absolute():
                source_path = (Path.cwd() / source_path).resolve()
            rules.extend(load_synonym_rules_from_file(source_path))

    return rules


def _fetch_rewrite(
    *,
    client: Any,
    collection: str,
    query_params: dict[str, Any],
    k: int,
    debug_mode: str,
) -> dict[str, Any]:
    params = dict(query_params)
    params["rows"] = str(k)
    params["fl"] = "id,score"
    params["wt"] = "json"
    if debug_mode == "results":
        params["debug"] = "query,results"
    else:
        params["debugQuery"] = "true"

    response = select(client, collection, params)
    info = extract_rewrite_info(response)
    if info.get("parsedquery") or info.get("parsedquery_toString"):
        return info

    fallback = dict(query_params)
    fallback["rows"] = str(k)
    fallback["fl"] = "id,score"
    fallback["wt"] = "json"
    fallback["debugQuery"] = "true"
    fallback_response = select(client, collection, fallback)
    return extract_rewrite_info(fallback_response)


def _select_diffs(
    diffs: list[dict[str, Any]],
    *,
    k: int,
    max_queries: int,
    always_for_high_risk: bool,
) -> list[dict[str, Any]]:
    ranked = _rank_diffs(diffs, k)[:max_queries]
    if not always_for_high_risk:
        return ranked

    selected_ids = {item.get("query_id") for item in ranked}
    for diff in _rank_diffs(diffs, k):
        if diff.get("risk_severity") != "HIGH":
            continue
        query_id = diff.get("query_id")
        if query_id in selected_ids:
            continue
        ranked.append(diff)
        selected_ids.add(query_id)
    return ranked


def run_rewrite_diff(
    *,
    baseline_client: Any,
    baseline_collection: str,
    shadow_client: Any,
    shadow_collection: str,
    replay_pairs: list[dict[str, Any]],
    diffs: list[dict[str, Any]],
    k: int,
    rewrite_cfg: dict[str, Any],
    synonym_rules: list[dict[str, Any]],
    has_synonym_changes: bool,
) -> dict[str, Any]:
    max_queries = int(rewrite_cfg.get("max_queries", 25))
    debug_mode = str(rewrite_cfg.get("debug_mode", "debugQuery"))
    if debug_mode not in {"debugQuery", "results"}:
        debug_mode = "debugQuery"
    clause_spike_threshold = int(rewrite_cfg.get("clause_spike_threshold", 5))
    always_for_high_risk = bool(rewrite_cfg.get("always_for_high_risk", True))

    selected_diffs = _select_diffs(
        diffs,
        k=k,
        max_queries=max_queries,
        always_for_high_risk=always_for_high_risk,
    )
    pairs_by_qid = {pair.get("query", {}).get("id"): pair for pair in replay_pairs}

    per_query: list[dict[str, Any]] = []
    for diff in selected_diffs:
        query_id = diff.get("query_id")
        pair = pairs_by_qid.get(query_id)
        if not pair:
            continue
        query = pair.get("query", {})
        raw_query = str(query.get("raw_line") or query.get("params", {}).get("q") or "")
        params = pair.get("effective_params")
        if not isinstance(params, dict):
            params = query.get("params", {})

        baseline_error = None
        shadow_error = None

        try:
            baseline_rewrite = _fetch_rewrite(
                client=baseline_client,
                collection=baseline_collection,
                query_params=params,
                k=k,
                debug_mode=debug_mode,
            )
        except Exception as exc:  # noqa: BLE001
            baseline_rewrite = {"parsedquery": None, "parsedquery_toString": None, "debug": {}}
            baseline_error = str(exc)

        try:
            shadow_rewrite = _fetch_rewrite(
                client=shadow_client,
                collection=shadow_collection,
                query_params=params,
                k=k,
                debug_mode=debug_mode,
            )
        except Exception as exc:  # noqa: BLE001
            shadow_rewrite = {"parsedquery": None, "parsedquery_toString": None, "debug": {}}
            shadow_error = str(exc)

        baseline_text = str(baseline_rewrite.get("parsedquery_toString") or "")
        shadow_text = str(shadow_rewrite.get("parsedquery_toString") or "")
        base_terms = _extract_terms(baseline_text)
        shadow_terms = _extract_terms(shadow_text)

        terms_added = sorted(shadow_terms - base_terms)
        terms_removed = sorted(base_terms - shadow_terms)
        clause_count_baseline = _clause_count(baseline_text)
        clause_count_shadow = _clause_count(shadow_text)
        clause_delta = clause_count_shadow - clause_count_baseline

        mm_value = params.get("mm") if isinstance(params, dict) else None
        mm_impact = None
        if mm_value is not None and clause_delta != 0:
            mm_impact = "clause_count_changed_under_mm"

        synonym_hints = _synonym_hints(
            raw_query=raw_query,
            baseline_text=baseline_text,
            shadow_text=shadow_text,
            synonym_rules=synonym_rules,
        )

        risk_flags: list[str] = []
        parsed_changed = baseline_text != shadow_text
        if parsed_changed:
            risk_flags.append("PARSED_QUERY_SHAPE_CHANGED")
        if clause_delta >= clause_spike_threshold:
            risk_flags.append("REWRITE_CLAUSE_SPIKE")
        if has_synonym_changes and (synonym_hints or terms_added or terms_removed):
            risk_flags.append("SYNONYM_EXPANSION_CHANGED")

        per_query.append(
            {
                "query_id": query_id,
                "raw_line": raw_query,
                "params": params,
                "baseline": baseline_rewrite,
                "shadow": shadow_rewrite,
                "clause_count_baseline": clause_count_baseline,
                "clause_count_shadow": clause_count_shadow,
                "clause_delta": clause_delta,
                "terms_added": terms_added,
                "terms_removed": terms_removed,
                "mm_value": mm_value,
                "mm_impact": mm_impact,
                "synonym_hints": synonym_hints,
                "risk_flags": risk_flags,
                "errors": {
                    "baseline": baseline_error,
                    "shadow": shadow_error,
                },
            }
        )

    top_clause = sorted(
        per_query,
        key=lambda item: abs(item.get("clause_delta", 0)),
        reverse=True,
    )[:20]
    top_synonym = [
        item
        for item in per_query
        if "SYNONYM_EXPANSION_CHANGED" in item.get("risk_flags", [])
    ][:20]

    return {
        "enabled": True,
        "debug_mode": debug_mode,
        "max_queries": max_queries,
        "always_for_high_risk": always_for_high_risk,
        "clause_spike_threshold": clause_spike_threshold,
        "queries_analyzed": len(per_query),
        "top_clause_deltas": top_clause,
        "top_synonym_changed": top_synonym,
        "per_query": per_query,
    }
