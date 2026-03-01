"""Extract query params from Solr/app request logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

INTERESTING_PARAMS = {
    "q",
    "fq",
    "defType",
    "qf",
    "pf",
    "sort",
    "mm",
    "tie",
    "boost",
    "rq",
    "rows",
}


def _merge_param(params: dict[str, Any], key: str, value: str) -> None:
    if key not in params:
        params[key] = value
        return
    prev = params[key]
    if isinstance(prev, list):
        prev.append(value)
    else:
        params[key] = [prev, value]


def _normalize_fq(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    if "fq" in out and not isinstance(out["fq"], list):
        out["fq"] = [out["fq"]]
    return out


def _extract_param_segment(line: str) -> str | None:
    text = line.strip()
    if not text:
        return None
    if "?" in text:
        text = text.split("?", 1)[1]
    if " " in text:
        text = text.split(" ", 1)[0]
    if "=" not in text:
        return None
    return text


def _from_json_line(text: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if isinstance(obj.get("params"), dict):
        return dict(obj["params"])
    for key in ("query", "query_string", "request", "url"):
        raw = obj.get(key)
        if isinstance(raw, str):
            segment = _extract_param_segment(raw)
            if segment:
                return parse_param_string(segment)
    if "q" in obj:
        return {
            k: v
            for k, v in obj.items()
            if isinstance(k, str)
        }
    return None


def parse_param_string(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in parse_qsl(raw, keep_blank_values=True):
        _merge_param(out, key, value)
    out = _normalize_fq(out)
    return {
        k: v
        for k, v in out.items()
        if k in INTERESTING_PARAMS or k not in {"wt"}
    }


def parse_log_line(line: str, fmt: str = "solr_params") -> dict[str, Any] | None:
    text = line.strip()
    if not text:
        return None

    if fmt == "jsonl" or text.startswith("{"):
        params = _from_json_line(text)
        return _normalize_fq(params) if params else None

    segment = _extract_param_segment(text)
    if not segment:
        return None
    return parse_param_string(segment)


def extract_queries_from_log(path: Path, fmt: str = "solr_params") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            params = parse_log_line(line, fmt=fmt)
            if not params:
                continue
            if "q" not in params:
                continue
            rows.append({"params": params, "source": {"line_no": line_no}})
    return rows

