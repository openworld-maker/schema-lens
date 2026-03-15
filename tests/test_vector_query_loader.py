from pathlib import Path

import pytest

from schema_lens.errors import ValidationError
from schema_lens.queries.loader import load_queries


def test_load_vector_queries_params_and_json_request(tmp_path: Path):
    query_file = tmp_path / "vector_queries.jsonl"
    query_file.write_text(
        "\n".join(
            [
                '{"name":"q1","params":{"q":"ss bolts"},"vector":[0.1,0.2,0.3]}',
                (
                    '{"name":"q2","json_request":{"query":"pump seal","limit":10},'
                    '"vector":[0.4,0.5,0.6]}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_queries(query_file, fmt="jsonl")
    assert len(cases) == 2
    assert cases[0].request_mode == "params"
    assert cases[0].params == {"q": "ss bolts"}
    assert cases[0].query_vector == [0.1, 0.2, 0.3]
    assert cases[1].request_mode == "json_request"
    assert cases[1].json_request == {"query": "pump seal", "limit": 10}
    assert cases[1].normalized_q == "pump seal"


def test_load_query_vector_from_knn_q(tmp_path: Path):
    query_file = tmp_path / "knn.jsonl"
    query_file.write_text(
        '{"params":{"q":"bearing","knn.q":"{!knn f=emb topK=10}[0.1,0.2,0.3]"}}\n',
        encoding="utf-8",
    )

    cases = load_queries(query_file, fmt="jsonl")
    assert len(cases) == 1
    # loader does not materialize query_vector when hidden in params; extraction happens downstream
    assert cases[0].query_vector is None


def test_load_queries_rejects_bad_json_request_shape(tmp_path: Path):
    query_file = tmp_path / "bad.jsonl"
    query_file.write_text('{"json_request":"bad"}\n', encoding="utf-8")

    with pytest.raises(ValidationError, match="invalid json_request"):
        load_queries(query_file, fmt="jsonl")
