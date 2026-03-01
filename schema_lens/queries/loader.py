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
                    params = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"Invalid JSONL query at line {line_no}") from exc
                if not isinstance(params, dict):
                    raise ValidationError(f"JSONL query at line {line_no} must be object")
                if isinstance(params.get("params"), dict):
                    params = params["params"]
                case = QueryCase(
                    id=len(cases) + 1,
                    line_no=line_no,
                    raw_line=stripped,
                    normalized_q=normalize_q(params),
                    fingerprint=query_fingerprint(params),
                    params=params,
                )
                cases.append(case)
                if max_queries and len(cases) >= max_queries:
                    break
    else:
        raise ValidationError(f"Unsupported query format: {fmt}")

    return cases
