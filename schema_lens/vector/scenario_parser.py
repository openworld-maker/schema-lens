"""Parse vector/hybrid runtime configuration from changeset + CLI overrides."""

from __future__ import annotations

from typing import Any

from schema_lens.vector.model import VectorRuntimeConfig, VectorScenario

_ALLOWED_MODES = {"lexical_only", "vector_only", "hybrid"}
_ALLOWED_BLEND_METHODS = {"linear", "normalize_linear", "rrf"}
_ALLOWED_EXECUTION = {"auto", "client", "solr_native"}
_ALLOWED_NORMALIZE = {"none", "minmax", "zscore"}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_sensitivity_weights(raw: Any, fallback: list[float]) -> list[float]:
    if not isinstance(raw, list) or not raw:
        return fallback
    out: list[float] = []
    for item in raw:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            continue
    return out or fallback


def parse_vector_runtime_config(
    *,
    changeset_vector: dict[str, Any] | None,
    evaluation_cfg: dict[str, Any] | None,
    default_top_k: int,
    selected_scenarios: list[str] | None = None,
    sensitivity_enabled_override: bool | None = None,
    sensitivity_weights_override: list[float] | None = None,
) -> VectorRuntimeConfig:
    vector_cfg = changeset_vector if isinstance(changeset_vector, dict) else {}
    eval_cfg = evaluation_cfg if isinstance(evaluation_cfg, dict) else {}

    enabled = bool(vector_cfg.get("enabled", False))
    field = str(vector_cfg.get("field", "emb"))
    dimension = vector_cfg.get("dimension")
    if dimension is not None:
        dimension = _as_int(dimension, 0) or None
    similarity_raw = vector_cfg.get("similarity")
    similarity = str(similarity_raw) if similarity_raw is not None else None
    query_vector_policy = str(vector_cfg.get("query_vector_policy", "skip"))

    vector_eval = eval_cfg.get("vector_hybrid", {}) if isinstance(eval_cfg, dict) else {}
    if not isinstance(vector_eval, dict):
        vector_eval = {}
    eval_enabled = bool(vector_eval.get("enabled", enabled))
    top_k = _as_int(vector_eval.get("topK"), default_top_k)
    if top_k <= 0:
        top_k = default_top_k
    candidate_pool = _as_int(vector_eval.get("candidate_pool"), max(100, top_k))
    if candidate_pool < top_k:
        candidate_pool = top_k

    sensitivity_cfg = vector_eval.get("sensitivity", {})
    if not isinstance(sensitivity_cfg, dict):
        sensitivity_cfg = {}
    sensitivity_enabled = bool(sensitivity_cfg.get("enabled", False))
    sensitivity_weights = _normalize_sensitivity_weights(
        sensitivity_cfg.get("weights"),
        [0.9, 0.7, 0.5, 0.3],
    )

    if sensitivity_enabled_override is not None:
        sensitivity_enabled = sensitivity_enabled_override
    if sensitivity_weights_override:
        sensitivity_weights = [float(w) for w in sensitivity_weights_override]

    scenarios_raw = vector_cfg.get("scenarios", [])
    scenarios: list[VectorScenario] = []
    if isinstance(scenarios_raw, list):
        for idx, raw in enumerate(scenarios_raw, start=1):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or f"scenario_{idx}")
            mode = str(raw.get("mode") or "lexical_only")
            if mode not in _ALLOWED_MODES:
                continue

            lexical = raw.get("lexical") if isinstance(raw.get("lexical"), dict) else {}
            knn = raw.get("knn") if isinstance(raw.get("knn"), dict) else {}
            blend = raw.get("blend") if isinstance(raw.get("blend"), dict) else {}

            if mode in {"vector_only", "hybrid"}:
                knn = {
                    **knn,
                    "field": str(knn.get("field") or field),
                    "k": _as_int(knn.get("k"), max(candidate_pool, top_k)),
                    "topK": _as_int(knn.get("topK"), top_k),
                }
                if knn["topK"] <= 0:
                    knn["topK"] = top_k
                if knn["k"] <= 0:
                    knn["k"] = max(candidate_pool, top_k)

            if mode == "hybrid":
                method = str(blend.get("method", "linear"))
                if method not in _ALLOWED_BLEND_METHODS:
                    method = "linear"
                execution = str(blend.get("execution", "auto"))
                if execution not in _ALLOWED_EXECUTION:
                    execution = "auto"
                normalize = str(blend.get("normalize", "none"))
                if normalize not in _ALLOWED_NORMALIZE:
                    normalize = "none"
                blend = {
                    "method": method,
                    "execution": execution,
                    "weight_lexical": _as_float(blend.get("weight_lexical"), 0.7),
                    "weight_vector": _as_float(blend.get("weight_vector"), 0.3),
                    "normalize": normalize,
                    "missing_vector_score": _as_float(
                        blend.get("missing_vector_score"),
                        0.0,
                    ),
                    "missing_lexical_score": _as_float(
                        blend.get("missing_lexical_score"),
                        0.0,
                    ),
                    "rrf_k": _as_int(blend.get("rrf_k"), 60),
                }

            scenarios.append(
                VectorScenario(
                    name=name,
                    mode=mode,
                    lexical={str(k): v for k, v in lexical.items()},
                    knn={str(k): v for k, v in knn.items()},
                    blend={str(k): v for k, v in blend.items()},
                )
            )

    if selected_scenarios:
        selected = {name for name in selected_scenarios}
        scenarios = [scenario for scenario in scenarios if scenario.name in selected]

    return VectorRuntimeConfig(
        enabled=enabled and eval_enabled and bool(scenarios),
        field=field,
        dimension=dimension,
        similarity=similarity,
        query_vector_policy=query_vector_policy,
        embedding_source=vector_cfg.get("embedding_source", {})
        if isinstance(vector_cfg.get("embedding_source"), dict)
        else {},
        scenarios=scenarios,
        evaluation={
            "enabled": eval_enabled,
            "topK": top_k,
            "candidate_pool": candidate_pool,
            "sensitivity": {
                "enabled": sensitivity_enabled,
                "weights": sensitivity_weights,
            },
            "comparison_mode": "lexical_anchor",
        },
    )
