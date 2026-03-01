"""Quality gate evaluation for compare outputs."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from schema_lens.queries.normalize import query_fingerprint


def _op_fn(op: str) -> Callable[[float, float], bool]:
    if op == "<":
        return lambda a, b: a < b
    if op == "<=":
        return lambda a, b: a <= b
    if op == ">":
        return lambda a, b: a > b
    if op == ">=":
        return lambda a, b: a >= b
    if op in {"=", "=="}:
        return lambda a, b: a == b
    raise ValueError(f"Unsupported operator: {op}")


def _overlap_ratio(diff: dict[str, Any], k: int) -> float:
    return float(diff.get("overlap_ratio", diff.get("topk_overlap_count", 0) / max(k, 1)))


def _collect_metrics(compare_data: dict[str, Any]) -> dict[str, float]:
    summary = compare_data.get("summary", {})
    diffs = compare_data.get("diffs", [])
    k = int(compare_data.get("k", 10))
    total = len(diffs) or 1
    high = len([d for d in diffs if d.get("risk_severity") == "HIGH"])
    medium = len([d for d in diffs if d.get("risk_severity") == "MEDIUM"])

    avg_overlap_ratio = summary.get("avg_overlap_ratio")
    if avg_overlap_ratio is None:
        avg_overlap = float(summary.get("avg_overlap", 0.0))
        avg_overlap_ratio = avg_overlap / max(k, 1)

    return {
        "avg_overlap": float(avg_overlap_ratio),
        "pct_high_risk_queries": float(summary.get("high_risk_percent", high / total * 100.0)),
        "pct_med_risk_queries": float(medium / total * 100.0),
        "_k": float(k),
    }


def _pct_queries_overlap_lt(compare_data: dict[str, Any], threshold: float) -> float:
    diffs = compare_data.get("diffs", [])
    if not diffs:
        return 0.0
    k = int(compare_data.get("k", 10))
    cnt = len([d for d in diffs if _overlap_ratio(d, k) < threshold])
    return cnt / len(diffs) * 100.0


def _metric_value(
    compare_data: dict[str, Any],
    metrics: dict[str, float],
    rule: dict[str, Any],
) -> float:
    metric = str(rule.get("metric"))
    if metric == "pct_queries_overlap_lt":
        threshold = float(rule.get("args", {}).get("threshold", 0.6))
        return _pct_queries_overlap_lt(compare_data, threshold)
    if metric not in metrics:
        raise ValueError(f"Unsupported metric in gate rule: {metric}")
    return float(metrics[metric])


def _read_golden_queries(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _evaluate_golden(
    compare_data: dict[str, Any],
    golden_cfg: dict[str, Any],
    *,
    policy_dir: Path,
) -> dict[str, Any]:
    enabled = bool(golden_cfg.get("enabled", False))
    if not enabled:
        return {"enabled": False, "failed": False, "results": []}

    golden_file = golden_cfg.get("file")
    if not isinstance(golden_file, str):
        raise ValueError("golden_queries.file is required when golden_queries.enabled=true")
    file_path = (policy_dir / golden_file).resolve()
    rows = _read_golden_queries(file_path)

    requirements = golden_cfg.get("requirements", {})
    default_must_contain_topk = int(
        requirements.get("must_contain_topk", compare_data.get("k", 10))
    )
    max_missing_pct = float(requirements.get("max_missing_pct", 0.0))

    by_fingerprint = {
        query_fingerprint(diff.get("params", {})): diff for diff in compare_data.get("diffs", [])
    }

    results = []
    failed = False
    for row in rows:
        params = row.get("params", {})
        expected_ids = [str(x) for x in row.get("expected_ids", [])]
        name = row.get("name", "golden")
        diff = by_fingerprint.get(query_fingerprint(params if isinstance(params, dict) else {}))

        if not expected_ids:
            results.append({"name": name, "status": "SKIP", "reason": "No expected_ids"})
            continue

        if not diff:
            missing = expected_ids
            missing_pct = 100.0
            shadow_topk = []
        else:
            row_topk = row.get("must_contain_topk", default_must_contain_topk)
            try:
                must_contain_topk = int(row_topk)
            except (TypeError, ValueError):
                must_contain_topk = default_must_contain_topk
            shadow_topk = [str(x) for x in diff.get("shadow_topk_ids", [])][:must_contain_topk]
            missing = [doc_id for doc_id in expected_ids if doc_id not in shadow_topk]
            missing_pct = len(missing) / len(expected_ids) * 100.0

        status = "PASS"
        if missing_pct > max_missing_pct:
            status = "FAIL"
            failed = True

        results.append(
            {
                "name": name,
                "status": status,
                "missing_ids": missing,
                "missing_pct": missing_pct,
                "expected_ids": expected_ids,
                "shadow_topk_ids": shadow_topk,
            }
        )

    return {"enabled": True, "failed": failed, "results": results}


def evaluate_gate(
    *,
    compare_data: dict[str, Any],
    policy_data: dict[str, Any],
    policy_dir: Path,
) -> dict[str, Any]:
    metrics = _collect_metrics(compare_data)
    failed_rules: list[dict[str, Any]] = []
    warned_rules: list[dict[str, Any]] = []

    for rule in policy_data.get("fail", []):
        value = _metric_value(compare_data, metrics, rule)
        target = float(rule.get("value"))
        op = str(rule.get("op"))
        if _op_fn(op)(value, target):
            failed_rules.append({**rule, "actual": value})

    for rule in policy_data.get("warn", []):
        value = _metric_value(compare_data, metrics, rule)
        target = float(rule.get("value"))
        op = str(rule.get("op"))
        if _op_fn(op)(value, target):
            warned_rules.append({**rule, "actual": value})

    golden = _evaluate_golden(
        compare_data,
        policy_data.get("golden_queries", {}),
        policy_dir=policy_dir,
    )

    passed = not failed_rules and not golden.get("failed", False)
    return {
        "pass": passed,
        "failed_rules": failed_rules,
        "warned_rules": warned_rules,
        "golden": golden,
        "metrics": {
            k: v for k, v in metrics.items() if not k.startswith("_")
        },
    }


def load_gate_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = yaml.safe_load(f)
    if not isinstance(obj, dict):
        raise ValueError("Gate policy must be a YAML object")
    return obj
