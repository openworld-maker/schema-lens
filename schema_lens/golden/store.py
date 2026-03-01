"""Golden query JSONL persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.golden.model import GoldenQuery
from schema_lens.util.io import ensure_dir


def append_golden(path: Path, golden: GoldenQuery) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(golden.to_dict(), sort_keys=False))
        f.write("\n")


def read_golden(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows

