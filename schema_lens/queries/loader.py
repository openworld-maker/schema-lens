"""Query loader utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from schema_lens.errors import ValidationError
from schema_lens.queries.model import QueryCase
from schema_lens.queries.normalize import normalize_q, query_fingerprint


def _merge_param(params: dict[str, Any], key: str, value: str) -> None:
    if key not in params:
        params[key] = value
        return
    prev = params[key]
    if isinstance(prev, list):
        prev.append(value)
    else:
        params[key] = [prev, value]


def _parse_param_string(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in parse_qsl(raw, keep_blank_values=True):
        _merge_param(out, k, v)
    return out


def _looks_like_param_string(text: str) -> bool:
    if "=" not in text:
        return False
    return "&" in text or text.split("=", 1)[0].isalnum()


def _coerce_query_vector(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    out: list[float] = []
    for item in value:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            return None
    return out or None


def _query_text_from_json_request(payload: dict[str, Any]) -> str:
    query = payload.get("query")
    if isinstance(query, str):
        return query
    params = payload.get("params")
    if isinstance(params, dict):
        q = params.get("q")
        if isinstance(q, str):
            return q
    return ""


def parse_simple_line(line: str) -> dict[str, Any]:
    text = line.strip()
    if not text:
        raise ValidationError("Empty query line")

    if text.startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON query line: {text}") from exc
        if not isinstance(obj, dict):
            raise ValidationError("JSON query line must be object")
        return obj

    if _looks_like_param_string(text):
        return _parse_param_string(text)

    return {"q": text}


def load_queries(
    path: Path,
    fmt: str = "simple",
    max_queries: int | None = None,
) -> list[QueryCase]:
    if not path.exists():
        raise ValidationError(f"Queries file not found: {path}")

    cases: list[QueryCase] = []
    if fmt == "simple":
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            params = parse_simple_line(stripped)
            case = QueryCase(
                id=len(cases) + 1,
                line_no=line_no,
                raw_line=stripped,
                normalized_q=normalize_q(params),
                fingerprint=query_fingerprint(params),
                params=params,
                request_mode="params",
                skip_reasons=[],
            )
            cases.append(case)
            if max_queries and len(cases) >= max_queries:
                break
    elif fmt == "jsonl":
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"Invalid JSONL query at line {line_no}") from exc
                if not isinstance(payload, dict):
                    raise ValidationError(f"JSONL query at line {line_no} must be object")

                name = payload.get("name")
                if name is not None and not isinstance(name, str):
                    name = str(name)
                params: dict[str, Any] | None = None
                json_request: dict[str, Any] | None = None
                request_mode = "params"

                if isinstance(payload.get("params"), dict):
                    params = payload["params"]
                elif isinstance(payload.get("json_request"), dict):
                    json_request = payload["json_request"]
                    request_mode = "json_request"
                elif "json_request" in payload and payload["json_request"] is not None:
                    raise ValidationError(
                        f"JSONL query at line {line_no} has invalid json_request object"
                    )
                else:
                    params = payload

                if isinstance(payload.get("json_request"), dict):
                    json_request = payload["json_request"]
                    if params is None:
                        request_mode = "json_request"

                query_vector = _coerce_query_vector(payload.get("vector"))
                normalized_q = normalize_q(params)
                if not normalized_q and isinstance(json_request, dict):
                    normalized_q = _query_text_from_json_request(json_request)
                fingerprint_payload: dict[str, Any] = {}
                if isinstance(params, dict):
                    fingerprint_payload["params"] = params
                if isinstance(json_request, dict):
                    fingerprint_payload["json_request"] = json_request
                if query_vector is not None:
                    fingerprint_payload["vector"] = query_vector

                case = QueryCase(
                    id=len(cases) + 1,
                    line_no=line_no,
                    raw_line=stripped,
                    normalized_q=normalized_q,
                    fingerprint=query_fingerprint(fingerprint_payload),
                    params=params,
                    name=name,
                    json_request=json_request,
                    query_vector=query_vector,
                    request_mode=request_mode,
                    skip_reasons=[],
                )
                cases.append(case)
                if max_queries and len(cases) >= max_queries:
                    break
    else:
        raise ValidationError(f"Unsupported query format: {fmt}")

    return cases
