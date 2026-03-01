"""Golden query discovery from extracted traffic sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.golden.model import GoldenQuery
from schema_lens.queries.normalize import query_fingerprint
from schema_lens.queries.sources.solr_request_log import extract_queries_from_log


def _read_rows(path: Path, fmt: str) -> list[dict[str, Any]]:
    if fmt == "log":
        return extract_queries_from_log(path, fmt="solr_params")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if not isinstance(obj, dict):
                continue
            params = obj.get("params", obj)
            if isinstance(params, dict) and "q" in params:
                row = {"params": params, "source": {"line_no": line_no}}
                if "frequency" in obj:
                    row["frequency"] = obj["frequency"]
                rows.append(row)
    return rows


def discover_golden_queries(
    *,
    path: Path,
    top: int,
    fmt: str = "jsonl",
    default_def_type: str = "edismax",
) -> list[GoldenQuery]:
    rows = _read_rows(path, fmt)

    counts: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    payload: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows):
        params = row.get("params", {})
        if not isinstance(params, dict):
            continue
        fp = query_fingerprint(params)
        weight = row.get("frequency", 1)
        try:
            freq = float(weight)
        except (TypeError, ValueError):
            freq = 1.0
        counts[fp] = counts.get(fp, 0.0) + freq
        first_seen.setdefault(fp, idx)
        payload.setdefault(fp, params)

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], first_seen[item[0]]),
    )

    results: list[GoldenQuery] = []
    for fp, _ in ranked[:top]:
        params = dict(payload[fp])
        params.setdefault("defType", default_def_type)
        q = str(params.get("q", "query"))
        name = q if len(q) <= 80 else f"{q[:77]}..."
        results.append(
            GoldenQuery(
                name=name,
                params=params,
                expected_ids=[],
                must_contain_topk=10,
            )
        )
    return results

