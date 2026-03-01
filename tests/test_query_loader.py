from pathlib import Path

import pytest

from schema_lens.errors import ValidationError
from schema_lens.queries.loader import load_queries, parse_simple_line


def test_parse_simple_raw_query():
    params = parse_simple_line("laptop")
    assert params == {"q": "laptop"}


def test_parse_param_string_query():
    params = parse_simple_line("q=phone&fq=category:electronics")
    assert params["q"] == "phone"
    assert params["fq"] == "category:electronics"


def test_parse_json_query():
    params = parse_simple_line('{"q":"wireless","fq":"category:electronics"}')
    assert params["q"] == "wireless"


def test_load_queries_simple_file(tmp_path):
    query_file = tmp_path / "queries.txt"
    query_file.write_text("laptop\nq=charger\n", encoding="utf-8")

    cases = load_queries(query_file, fmt="simple")
    assert len(cases) == 2
    assert cases[0].normalized_q == "laptop"
    assert cases[1].params["q"] == "charger"


def test_parse_repeated_query_params():
    params = parse_simple_line("q=phone&fq=a&fq=b")
    assert params["q"] == "phone"
    assert params["fq"] == ["a", "b"]


def test_load_queries_jsonl_format(tmp_path: Path):
    query_file = tmp_path / "queries.jsonl"
    query_file.write_text('{"q":"foo"}\n{"q":"bar","fq":"cat:x"}\n', encoding="utf-8")
    cases = load_queries(query_file, fmt="jsonl")
    assert len(cases) == 2
    assert cases[1].params["fq"] == "cat:x"


def test_load_queries_jsonl_invalid_line(tmp_path: Path):
    query_file = tmp_path / "queries.jsonl"
    query_file.write_text("{bad}\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Invalid JSONL query"):
        load_queries(query_file, fmt="jsonl")
