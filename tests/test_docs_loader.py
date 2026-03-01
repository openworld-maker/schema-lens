from pathlib import Path

import pytest

from schema_lens.data.docs_loader import load_docs
from schema_lens.errors import ValidationError


def test_load_docs_jsonl_with_sampling(tmp_path: Path):
    docs_path = tmp_path / "docs.jsonl"
    docs_path.write_text(
        '{"id":"1","title":"a"}\n{"id":"2","title":"b"}\n',
        encoding="utf-8",
    )

    docs = load_docs(docs_path, fmt="jsonl", sample_n=1)
    assert len(docs) == 1
    assert docs[0]["id"] == "1"


def test_load_docs_json_array(tmp_path: Path):
    docs_path = tmp_path / "docs.json"
    docs_path.write_text('[{"id":"1"},{"id":"2"}]', encoding="utf-8")

    docs = load_docs(docs_path, fmt="json")
    assert len(docs) == 2


@pytest.mark.parametrize(
    ("payload", "fmt", "msg"),
    [
        ("{bad", "json", "Invalid JSON file"),
        ("{\"id\":\"1\"}", "json", "must contain an array"),
        ("42\n", "jsonl", "must be object"),
    ],
)
def test_load_docs_invalid_payloads(tmp_path: Path, payload: str, fmt: str, msg: str):
    path = tmp_path / f"docs.{fmt}"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValidationError, match=msg):
        load_docs(path, fmt=fmt)


def test_load_docs_missing_id_field(tmp_path: Path):
    docs_path = tmp_path / "docs.jsonl"
    docs_path.write_text('{"title":"x"}\n', encoding="utf-8")

    with pytest.raises(ValidationError, match="missing id field"):
        load_docs(docs_path, fmt="jsonl", id_field="id")


def test_load_docs_unsupported_format(tmp_path: Path):
    docs_path = tmp_path / "docs.any"
    docs_path.write_text('{"id":"1"}\n', encoding="utf-8")

    with pytest.raises(ValidationError, match="Unsupported docs format"):
        load_docs(docs_path, fmt="csv")
