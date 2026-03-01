"""Changeset parser."""

from __future__ import annotations

from pathlib import Path

import yaml

from schema_lens.changesets.model import Changeset
from schema_lens.errors import ValidationError


def parse_changeset(path: Path) -> Changeset:
    if not path.exists():
        raise ValidationError(f"Changeset file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValidationError("Changeset must be a YAML mapping/object")

    return Changeset(raw=raw, path=path)
