"""Retention policy enforcement for artifacts."""

from __future__ import annotations

from pathlib import Path


SENSITIVE_ARTIFACTS = {
    "docs_sample.jsonl",
    "queries_extracted.jsonl",
    "replay.json",
}


def enforce_retention(out_dir: Path, *, persist_sensitive: bool) -> list[str]:
    deleted: list[str] = []
    if persist_sensitive:
        return deleted
    for name in SENSITIVE_ARTIFACTS:
        path = out_dir / name
        if path.exists() and path.is_file():
            path.unlink()
            deleted.append(name)
    return deleted
