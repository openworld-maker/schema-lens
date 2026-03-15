"""Monitor state persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.util.io import write_json, write_jsonl


def persist_monitor_state(
    *,
    out_dir: Path,
    latest: dict[str, Any],
    history: list[dict[str, Any]],
) -> None:
    write_json(out_dir / "latest_monitor.json", latest)
    write_jsonl(out_dir / "monitor_history.jsonl", history)
