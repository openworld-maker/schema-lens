"""Build vector/hybrid Solr requests from query cases."""

from __future__ import annotations

import copy
import re
from typing import Any

from schema_lens.queries.model import QueryCase

_VECTOR_PATTERN = re.compile(r"\[(?P<body>[^\]]+)\]")


def _coerce_vector(raw: Any) -> list[float] | None:
    if not isinstance(raw, list):
        return None
    values: list[float] = []
    for item in raw:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            return None
    return values or None


def _vector_from_knn_q(knn_q: Any) -> list[float] | None:
    if not isinstance(knn_q, str):
        return None
    match = _VECTOR_PATTERN.search(knn_q)
    if not match:
        return None
    body = match.group("body").strip()
    if not body:
        return None
    values: list[float] = []
    for token in body.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(float(token))
        except (TypeError, ValueError):
            return None
    return values or None


def extract_query_vector(query_case: QueryCase) -> list[float] | None:
    explicit = _coerce_vector(query_case.query_vector)
    if explicit is not None:
        return explicit

    if isinstance(query_case.params, dict):
        knn_q = query_case.params.get("knn.q")
        parsed = _vector_from_knn_q(knn_q)
        if parsed is not None:
            return parsed

    if isinstance(query_case.json_request, dict):
        queries = query_case.json_request.get("queries")
        if isinstance(queries, dict):
            for entry in queries.values():
                if not isinstance(entry, dict):
                    continue
                raw_vec = entry.get("vector")
                parsed = _coerce_vector(raw_vec)
                if parsed is not None:
                    return parsed
    return None


def format_knn_query(*, field: str, top_k: int, vector: list[float]) -> str:
    vector_text = ",".join(f"{value:.8g}" for value in vector)
    return f"{{!knn f={field} topK={top_k}}}[{vector_text}]"


def build_lexical_request(
    *,
    query_case: QueryCase,
    rows: int,
    base_defaults: dict[str, Any] | None = None,
    lexical_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_defaults = base_defaults or {}
    lexical_overrides = lexical_overrides or {}

    if query_case.request_mode == "json_request" and isinstance(query_case.json_request, dict):
        body = copy.deepcopy(query_case.json_request)
        body["limit"] = rows
        if "rows" in body:
            body["rows"] = rows
        params = body.get("params")
        if not isinstance(params, dict):
            params = {}
            body["params"] = params
        params.update({str(k): v for k, v in base_defaults.items()})
        params.update({str(k): v for k, v in lexical_overrides.items()})
        params.setdefault("fl", "id,score")
        return {
            "mode": "json_request",
            "json_body": body,
            "params": {"wt": "json"},
        }

    params: dict[str, Any] = {}
    params.update({str(k): v for k, v in base_defaults.items()})
    if isinstance(query_case.params, dict):
        params.update(query_case.params)
    params.update({str(k): v for k, v in lexical_overrides.items()})
    params["rows"] = str(rows)
    params["fl"] = str(params.get("fl", "id,score"))
    if "id" not in params["fl"]:
        params["fl"] = f"{params['fl']},id"
    if "score" not in params["fl"]:
        params["fl"] = f"{params['fl']},score"
    params["wt"] = "json"
    return {
        "mode": "params",
        "params": params,
    }


def build_vector_request(
    *,
    query_case: QueryCase,
    field: str,
    top_k: int,
    rows: int,
) -> tuple[dict[str, Any] | None, str | None]:
    vector = extract_query_vector(query_case)
    if not vector:
        return None, "missing_query_vector"

    params: dict[str, Any] = {
        "q": format_knn_query(field=field, top_k=top_k, vector=vector),
        "rows": str(rows),
        "fl": "id,score",
        "wt": "json",
    }

    if isinstance(query_case.params, dict):
        for key in ("fq",):
            if key in query_case.params:
                params[key] = query_case.params[key]
    elif isinstance(query_case.json_request, dict):
        filters = query_case.json_request.get("filter")
        if isinstance(filters, list):
            params["fq"] = [str(item) for item in filters if item is not None]
        elif isinstance(filters, str):
            params["fq"] = filters

    return {
        "mode": "params",
        "params": params,
    }, None


def detect_native_hybrid_request(query_case: QueryCase) -> bool:
    if not isinstance(query_case.json_request, dict):
        return False
    body = query_case.json_request
    if "queries" in body and isinstance(body.get("queries"), dict):
        queries = body["queries"]
        for entry in queries.values():
            if isinstance(entry, dict) and str(entry.get("type", "")).lower() == "knn":
                return True
    query_value = body.get("query")
    if isinstance(query_value, str) and "{!knn" in query_value:
        return True
    return False
