from pathlib import Path

from schema_lens.queries.sampler import sample_queries
from schema_lens.queries.sanitize import sanitize_params
from schema_lens.queries.sources.solr_request_log import (
    extract_queries_from_log,
    parse_log_line,
)


def test_parse_log_line_param_string():
    params = parse_log_line("q=bolts&fq=category:tools&defType=edismax")
    assert params["q"] == "bolts"
    assert params["fq"] == ["category:tools"]


def test_parse_log_line_path_prefixed():
    params = parse_log_line("/browse/select?q=pipes&sort=price%20asc")
    assert params["q"] == "pipes"
    assert params["sort"] == "price asc"


def test_parse_log_line_json():
    params = parse_log_line('{"params":{"q":"bearings","fq":["cat:a"]}}', fmt="jsonl")
    assert params["q"] == "bearings"
    assert params["fq"] == ["cat:a"]


def test_sanitize_masks_and_drops():
    clean = sanitize_params(
        {
            "q": "user@example.com 550e8400-e29b-41d4-a716-446655440000",
            "token": "secret",
        },
        enabled=True,
    )
    assert clean["q"] == "<redacted_email> <redacted_uuid>"
    assert "token" not in clean


def test_extract_and_sample_reservoir_deterministic(tmp_path: Path):
    log_path = tmp_path / "req.log"
    log_path.write_text(
        "\n".join(
            [
                "q=a",
                "q=b",
                "q=c",
                "q=d",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = extract_queries_from_log(log_path)
    s1 = sample_queries(rows, mode="reservoir", max_queries=2, seed=42)
    s2 = sample_queries(rows, mode="reservoir", max_queries=2, seed=42)
    assert s1 == s2


def test_extract_and_sample_top(tmp_path: Path):
    log_path = tmp_path / "req.log"
    log_path.write_text("q=a\nq=a\nq=b\n", encoding="utf-8")
    rows = extract_queries_from_log(log_path)
    sampled = sample_queries(rows, mode="top", max_queries=1)
    assert len(sampled) == 1
    assert sampled[0]["params"]["q"] == "a"

