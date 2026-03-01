"""Document loading utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.data.docs_sampler import sample_docs
from schema_lens.errors import ValidationError


def _detect_format(path: Path, declared: str | None) -> str:
    if declared:
        return declared
    return "jsonl" if path.suffix.lower() == ".jsonl" else "json"


def load_docs(
    path: Path,
    fmt: str | None = None,
    id_field: str = "id",
    sample_n: int | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValidationError(f"Docs file not found: {path}")

    resolved_format = _detect_format(path, fmt)

    docs: list[dict[str, Any]]
    if resolved_format == "jsonl":
        docs = []
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"Invalid JSONL at {path}:{line_no}") from exc
                if not isinstance(obj, dict):
                    raise ValidationError(f"JSONL record at {path}:{line_no} must be object")
                docs.append(obj)
    elif resolved_format == "json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON file: {path}") from exc
        if not isinstance(payload, list):
            raise ValidationError(f"JSON docs file must contain an array: {path}")
        docs = []
        for i, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValidationError(f"Doc at index {i} in {path} must be object")
            docs.append(item)
    else:
        raise ValidationError(f"Unsupported docs format: {resolved_format}")

    for i, doc in enumerate(docs):
        if id_field not in doc:
            raise ValidationError(f"Doc at index {i} missing id field '{id_field}'")

    return sample_docs(docs, sample_n)
