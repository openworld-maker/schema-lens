"""Retention policy enforcement for artifacts."""

from __future__ import annotations

from pathlib import Path


SENSITIVE_ARTIFACTS = {
    "docs_sample.jsonl",
    "queries_extracted.jsonl",
    "replay.json",
}

SUMMARY_ONLY_EXTRA_ARTIFACTS = {
    "compare.json",
    "env_compare.json",
    "rootcauses.json",
    "recommendations.json",
    "perf_metrics.json",
    "ltr_impact.json",
    "plugins.json",
    "queries_scored.jsonl",
}


def enforce_retention(out_dir: Path, *, persist_sensitive: bool, summary_only: bool = False) -> list[str]:
    deleted: list[str] = []
    targets = set(SENSITIVE_ARTIFACTS)
    if summary_only:
        targets.update(SUMMARY_ONLY_EXTRA_ARTIFACTS)
    if persist_sensitive and not summary_only:
        return deleted
    for name in targets:
        path = out_dir / name
        if path.exists() and path.is_file():
            path.unlink()
            deleted.append(name)
    return deleted
