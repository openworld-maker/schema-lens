"""Patch configset text resources (synonyms/stopwords) deterministically."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from schema_lens.changesets.operations import CONFIGSET_OPS
from schema_lens.errors import ValidationError

CONFIGSET_UPDATE_MODES = {"replace", "patch_append", "patch_merge"}


def has_configset_updates(changes: list[dict[str, Any]]) -> bool:
    return any(op.get("op") in CONFIGSET_OPS for op in changes)


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines)
    if lines:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def _dedupe_merge(existing: list[str], patch: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for line in [*existing, *patch]:
        key = line.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        merged.append(key)
    return merged


def _apply_mode(existing: list[str], patch: list[str], mode: str) -> list[str]:
    if mode == "replace":
        return [line.strip() for line in patch if line.strip()]
    if mode == "patch_append":
        base = [line.strip() for line in existing if line.strip()]
        extra = [line.strip() for line in patch if line.strip()]
        return [*base, *extra]
    if mode == "patch_merge":
        base = [line.strip() for line in existing if line.strip()]
        extra = [line.strip() for line in patch if line.strip()]
        return _dedupe_merge(base, extra)
    raise ValidationError(f"Unsupported configset patch mode: {mode}")


def _resolve_source(
    op: dict[str, Any],
    file_entry: dict[str, Any],
    *,
    changeset_path: Path | None,
) -> Path:
    raw = file_entry.get("source_file", op.get("source_file"))
    if not isinstance(raw, str) or not raw:
        raise ValidationError("schema synonym/stopwords update op requires source_file")
    source = Path(raw)
    if source.is_absolute() and source.exists():
        return source

    candidates: list[Path] = []
    if changeset_path is not None:
        candidates.append((changeset_path.parent / source).resolve())
    candidates.append((Path.cwd() / source).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else source


def _resolve_target(file_entry: dict[str, Any], configset_dir: Path) -> Path:
    raw = file_entry.get("path")
    if not isinstance(raw, str) or not raw:
        raise ValidationError("target.files[].path is required for configset update ops")
    normalized = raw.lstrip("/")
    return (configset_dir / normalized).resolve()


def apply_configset_updates(
    *,
    configset_dir: Path,
    changes: list[dict[str, Any]],
    changeset_path: Path | None,
) -> dict[str, Any]:
    configset_root = configset_dir.resolve()
    applied: list[dict[str, Any]] = []

    for op in changes:
        op_name = op.get("op")
        if op_name not in CONFIGSET_OPS:
            continue

        target = op.get("target", {})
        files = target.get("files", []) if isinstance(target, dict) else []
        if not isinstance(files, list) or not files:
            raise ValidationError(f"{op_name} requires target.files")

        default_mode = str(op.get("mode", ""))
        if default_mode and default_mode not in CONFIGSET_UPDATE_MODES:
            raise ValidationError(f"Unsupported configset mode: {default_mode}")

        for idx, entry in enumerate(files):
            if not isinstance(entry, dict):
                raise ValidationError(f"{op_name}.target.files[{idx}] must be object")
            mode = str(entry.get("mode", default_mode or "replace"))
            if mode not in CONFIGSET_UPDATE_MODES:
                raise ValidationError(f"Unsupported configset mode: {mode}")

            source_file = _resolve_source(op, entry, changeset_path=changeset_path)
            if not source_file.exists():
                raise ValidationError(f"Configset source_file not found: {source_file}")

            target_file = _resolve_target(entry, configset_dir)
            existing_lines = _read_lines(target_file)
            patch_lines = _read_lines(source_file)
            updated_lines = _apply_mode(existing_lines, patch_lines, mode)
            _write_lines(target_file, updated_lines)

            applied.append(
                {
                    "op": op_name,
                    "target_path": str(target_file.resolve().relative_to(configset_root)),
                    "mode": mode,
                    "source_file": str(source_file),
                    "line_count_before": len(existing_lines),
                    "line_count_after": len(updated_lines),
                }
            )

    return {"applied": applied}


def hash_directory(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted([p for p in path.rglob("*") if p.is_file()], key=lambda p: p.as_posix())
    for file_path in files:
        rel = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(rel)
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def parse_synonym_rules(lines: list[str]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "=>" in line:
            left, right = [part.strip() for part in line.split("=>", 1)]
            src_terms = [term.strip().lower() for term in left.split(",") if term.strip()]
            dst_terms = [term.strip().lower() for term in right.split(",") if term.strip()]
            for src in src_terms:
                if dst_terms:
                    rules.append({"source": src, "targets": dst_terms})
            continue

        terms = [term.strip().lower() for term in line.split(",") if term.strip()]
        for src in terms:
            others = [term for term in terms if term != src]
            if others:
                rules.append({"source": src, "targets": others})
    return rules


def load_synonym_rules_from_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return parse_synonym_rules(path.read_text(encoding="utf-8").splitlines())
