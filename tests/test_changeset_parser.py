from pathlib import Path

import pytest

from schema_lens.changesets.parser import parse_changeset
from schema_lens.errors import ValidationError


def test_parse_changeset_missing_file(tmp_path: Path):
    with pytest.raises(ValidationError, match="file not found"):
        parse_changeset(tmp_path / "missing.yaml")


def test_parse_changeset_invalid_yaml(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("baseline: [", encoding="utf-8")

    with pytest.raises(ValidationError, match="Invalid YAML"):
        parse_changeset(path)


def test_parse_changeset_non_mapping(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("- item", encoding="utf-8")

    with pytest.raises(ValidationError, match="must be a YAML mapping"):
        parse_changeset(path)


def test_parse_changeset_valid(tmp_path: Path):
    path = tmp_path / "good.yaml"
    path.write_text("baseline:\n  solr_url: http://localhost\n", encoding="utf-8")

    changeset = parse_changeset(path)
    assert changeset.path == path
    assert "baseline" in changeset.raw
