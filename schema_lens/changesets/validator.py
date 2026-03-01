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

    required = ["baseline.solr_url", "baseline.collection"]
    for key in required:
        if _get_in(raw, key) in (None, ""):
            report.errors.append(f"Missing required field: {key}")

    docs_source = _get_in(raw, "data.docs_source") or {}
    if not isinstance(docs_source, dict):
        report.errors.append("data.docs_source must be an object")
        docs_source = {}
    docs_source_type = str(docs_source.get("type", "file"))
    if docs_source_type not in {"file", "solr"}:
        report.errors.append("data.docs_source.type must be 'file' or 'solr'")
    if docs_source_type == "file":
        if not docs_source.get("path"):
            report.errors.append("Missing required field: data.docs_source.path")
    else:
        for key in ("solr_url", "collection"):
            if not docs_source.get(key):
                report.errors.append(f"Missing required field: data.docs_source.{key}")
        mode = docs_source.get("mode")
        if mode and mode not in {"export", "cursormark"}:
            report.errors.append("data.docs_source.mode must be 'export' or 'cursormark'")

    query_source = _get_in(raw, "queries.source") or {}
    if not isinstance(query_source, dict):
        report.errors.append("queries.source must be an object")
        query_source = {}
    query_source_type = str(query_source.get("type", "file"))
    if query_source_type not in {"file", "log"}:
        report.errors.append("queries.source.type must be 'file' or 'log'")
    if not query_source.get("path"):
        report.errors.append("Missing required field: queries.source.path")

    if query_source_type == "log":
        fmt = str(query_source.get("format", "solr_params"))
        if fmt not in {"solr_params", "jsonl"}:
            report.errors.append("queries.source.format must be 'solr_params' or 'jsonl'")

    sampling_mode = _get_in(raw, "queries.sampling.mode")
    if sampling_mode is not None and sampling_mode not in {"top", "reservoir"}:
        report.errors.append("queries.sampling.mode must be 'top' or 'reservoir'")

    preflight_fail = _get_in(raw, "preflight.fail_on_risk")
    if preflight_fail is not None and not isinstance(preflight_fail, bool):
        report.errors.append("preflight.fail_on_risk must be boolean")

    replay_capture = _get_in(raw, "replay.capture")
    if replay_capture is not None and not isinstance(replay_capture, dict):
        report.errors.append("replay.capture must be an object")
    if isinstance(replay_capture, dict):
        facets = replay_capture.get("facets")
        if facets is not None and not isinstance(facets, dict):
            report.errors.append("replay.capture.facets must be an object")
        if isinstance(facets, dict):
            enabled = facets.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                report.errors.append("replay.capture.facets.enabled must be boolean")
            if facets.get("enabled"):
                fields = facets.get("fields")
                if not isinstance(fields, list) or not all(isinstance(x, str) for x in fields):
                    report.errors.append(
                        "replay.capture.facets.fields must be a list of strings "
                        "when facets are enabled"
                    )
            limit = facets.get("limit")
            if limit is not None:
                try:
                    if int(limit) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    report.errors.append("replay.capture.facets.limit must be an integer > 0")
        for field_name in ("track_numfound", "track_sort"):
            field_val = replay_capture.get(field_name)
            if field_val is not None and not isinstance(field_val, bool):
                report.errors.append(f"replay.capture.{field_name} must be boolean")

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
        docs_path = _get_in(raw, "data.docs_source.path") if docs_source_type == "file" else None
        queries_path = _get_in(raw, "queries.source.path")
        path_entries = [("queries.source.path", queries_path)]
        if docs_path is not None:
            path_entries.append(("data.docs_source.path", docs_path))
        for label, p in path_entries:
            if isinstance(p, str):
                fp = _resolve_input_path(changeset.path, p)
                if not fp.exists():
                    report.errors.append(f"{label} does not exist: {fp}")

    return report
