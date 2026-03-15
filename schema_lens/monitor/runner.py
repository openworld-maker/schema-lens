"""One-shot drift monitoring based on a prior run or snapshot directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.compare.diff import compare_replay
from schema_lens.monitor.drift import compute_drift_summary
from schema_lens.monitor.report import summarize_monitor
from schema_lens.monitor.scheduler import normalize_interval
from schema_lens.monitor.state import persist_monitor_state
from schema_lens.snapshot.snapshotter import load_snapshot
from schema_lens.util.io import read_json
from schema_lens.util.time import utc_now_iso


def _load_optional(path: Path) -> dict[str, Any] | None:
    if path.exists():
        payload = read_json(path)
        if isinstance(payload, dict):
            return payload
    return None


def _build_current_from_baseline_replay(
    *,
    baseline_replay: dict[str, Any],
) -> dict[str, Any]:
    pairs = baseline_replay.get("pairs", [])
    synthetic_pairs: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        synthetic_pairs.append(
            {
                "query": pair.get("query", {}),
                "baseline": pair.get("baseline", {}),
                "shadow": pair.get("baseline", {}),
            }
        )
    return {"k": baseline_replay.get("k", 10), "pairs": synthetic_pairs}


def run_monitor(
    *,
    baseline_snapshot_dir: Path,
    queries_path: Path,
    query_format: str,
    interval: str,
    out_dir: Path,
) -> dict[str, Any]:
    snapshot = load_snapshot(baseline_snapshot_dir)
    baseline_report = _load_optional(baseline_snapshot_dir / "report.json")
    baseline_replay = _load_optional(baseline_snapshot_dir / "replay.json")

    # First cut: if a baseline replay/report exists in the run directory, reuse it.
    current_report = baseline_report
    current_compare = None
    if baseline_replay:
        current_replay = _build_current_from_baseline_replay(baseline_replay=baseline_replay)
        current_compare = compare_replay(current_replay, int(current_replay.get("k", 10)))
        current_report = {
            "summary": current_compare.get("summary", {}),
            "per_query_diffs": current_compare.get("diffs", []),
        }

    history_path = out_dir / "monitor_history.jsonl"
    history: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                history.append(payload)

    latest = {
        "enabled": True,
        "baseline_snapshot_hash": snapshot.get("hash"),
        "interval": normalize_interval(interval),
        "checked_at": utc_now_iso(),
        "queries_path": str(queries_path),
        "query_format": query_format,
        "drift": compute_drift_summary(baseline_report, current_report),
        "schema_hash_changed": False,
        "summaries": [],
    }
    latest["summaries"] = summarize_monitor(latest)
    history.append(latest)
    persist_monitor_state(out_dir=out_dir, latest=latest, history=history)
    return {
        "latest": latest,
        "history": history,
        "compare": current_compare
        or {"enabled": False, "reason": "No baseline replay.json present"},
    }
