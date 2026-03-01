from pathlib import Path

from schema_lens.golden.discover import discover_golden_queries
from schema_lens.golden.model import GoldenQuery
from schema_lens.golden.store import append_golden, read_golden


def test_golden_add_store_appends_jsonl(tmp_path: Path):
    path = tmp_path / "golden.jsonl"
    append_golden(
        path,
        GoldenQuery(
            name="bearing",
            params={"q": "bearing", "defType": "edismax"},
            expected_ids=["B-001"],
            must_contain_topk=10,
        ),
    )
    rows = read_golden(path)
    assert len(rows) == 1
    assert rows[0]["expected_ids"] == ["B-001"]


def test_golden_discover_top_n(tmp_path: Path):
    source = tmp_path / "queries.jsonl"
    source.write_text(
        "\n".join(
            [
                '{"params":{"q":"a"},"frequency":10}',
                '{"params":{"q":"b"},"frequency":2}',
                '{"params":{"q":"a"},"frequency":1}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = discover_golden_queries(path=source, top=1, fmt="jsonl", default_def_type="edismax")
    assert len(out) == 1
    assert out[0].params["q"] == "a"
    assert out[0].expected_ids == []

