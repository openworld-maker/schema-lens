"""Changeset validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schema_lens.changesets.model import Changeset
from schema_lens.changesets.operations import SUPPORTED_OPS


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _get_in(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _resolve_input_path(base_file: Path | None, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    candidates = []
    if base_file is not None:
        candidates.append((base_file.parent / path).resolve())
    candidates.append((Path.cwd() / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def validate_changeset(changeset: Changeset, check_paths: bool = True) -> ValidationReport:
    report = ValidationReport()
    raw = changeset.raw
    version = raw.get("schema_lens_version")
    if version not in (None, 1):
        report.errors.append(f"Unsupported schema_lens_version: {version}")

    required = [
        "baseline.solr_url",
        "baseline.collection",
        "data.docs_source.path",
        "queries.source.path",
    ]
    for key in required:
        if _get_in(raw, key) in (None, ""):
            report.errors.append(f"Missing required field: {key}")

    changes = raw.get("changes", [])
    if not isinstance(changes, list):
        report.errors.append("changes must be a list")
        changes = []

    if not changes:
        report.warnings.append("No changes specified; run will still execute query replay")

    for idx, op in enumerate(changes):
        loc = f"changes[{idx}]"
        if not isinstance(op, dict):
            report.errors.append(f"{loc} must be an object")
            continue

        op_name = op.get("op")
        if op_name not in SUPPORTED_OPS:
            report.errors.append(f"{loc}.op unsupported: {op_name}")
            continue

        if op_name == "schema.field.update":
            if not op.get("field"):
                report.errors.append(f"{loc}.field is required")
            if not isinstance(op.get("set"), dict):
                report.errors.append(f"{loc}.set must be an object")

        if op_name == "schema.fieldType.replace":
            if not op.get("name") or not op.get("with"):
                report.errors.append(f"{loc}.name and {loc}.with are required")

        if op_name == "schema.analyzer.remove_filter":
            required_keys = ["fieldType", "analyzer", "filter_class"]
            for rk in required_keys:
                if not op.get(rk):
                    report.errors.append(f"{loc}.{rk} is required")
            if op.get("analyzer") not in (None, "index", "query"):
                report.errors.append(f"{loc}.analyzer must be 'index' or 'query'")

        if op_name == "queryparams.set" and not isinstance(op.get("set"), dict):
            report.errors.append(f"{loc}.set must be an object")

    if check_paths:
        docs_path = _get_in(raw, "data.docs_source.path")
        queries_path = _get_in(raw, "queries.source.path")
        path_entries = (
            ("data.docs_source.path", docs_path),
            ("queries.source.path", queries_path),
        )
        for label, p in path_entries:
            if isinstance(p, str):
                fp = _resolve_input_path(changeset.path, p)
                if not fp.exists():
                    report.errors.append(f"{label} does not exist: {fp}")

    return report
