from pathlib import Path

from schema_lens.queries.model import QueryCase
from schema_lens.vector.model import VectorRuntimeConfig, VectorScenario
from schema_lens.vector.validation import (
    augment_docs_with_embeddings,
    load_embeddings,
    validate_vector_setup,
)


def _runtime_cfg(policy: str = "skip") -> VectorRuntimeConfig:
    return VectorRuntimeConfig(
        enabled=True,
        field="emb",
        dimension=8,
        similarity="cosine",
        query_vector_policy=policy,
        embedding_source={"type": "none"},
        scenarios=[
            VectorScenario(name="lexical_only", mode="lexical_only"),
            VectorScenario(
                name="vector_only",
                mode="vector_only",
                knn={"field": "emb", "k": 20, "topK": 10},
            ),
        ],
        evaluation={"topK": 10, "candidate_pool": 50},
    )


def _schema(dim: int = 8) -> dict:
    return {
        "schema": {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "emb", "type": "vector_8", "vectorDimension": dim},
            ],
            "fieldTypes": [
                {"name": "string", "class": "solr.StrField"},
                {
                    "name": "vector_8",
                    "class": "solr.DenseVectorField",
                    "vectorDimension": dim,
                    "similarityFunction": "cosine",
                },
            ],
        }
    }


def test_validate_vector_setup_dimension_mismatch_blocks():
    queries = [
        QueryCase(
            id=1,
            line_no=1,
            raw_line='{"params":{"q":"a"},"vector":[0,1,2]}',
            params={"q": "a"},
            normalized_q="a",
            fingerprint="x",
            query_vector=[0.0, 1.0, 2.0],
        )
    ]
    result = validate_vector_setup(
        baseline_schema=_schema(dim=8),
        vector_cfg=_runtime_cfg(),
        query_cases=queries,
        vector_dimension_override=None,
    )
    assert result["block_run"] is True
    assert any(f["code"] == "QUERY_VECTOR_DIMENSION_MISMATCH" for f in result["findings"])


def test_validate_vector_setup_missing_vectors_fail_policy_blocks():
    queries = [
        QueryCase(
            id=1,
            line_no=1,
            raw_line='{"params":{"q":"a"}}',
            params={"q": "a"},
            normalized_q="a",
            fingerprint="x",
        )
    ]
    result = validate_vector_setup(
        baseline_schema=_schema(dim=8),
        vector_cfg=_runtime_cfg(policy="fail"),
        query_cases=queries,
        vector_dimension_override=None,
    )
    assert result["block_run"] is True
    assert result["stats"]["missing_query_vectors"] == 1


def test_load_embeddings_and_augment_docs(tmp_path: Path):
    emb = tmp_path / "emb.jsonl"
    emb.write_text(
        '{"id":"1","emb":[0.1,0.2]}\n{"id":"2","emb":[0.2,0.3]}\n',
        encoding="utf-8",
    )

    mapping, source_type = load_embeddings(
        embedding_source={
            "type": "file",
            "path": str(emb),
            "id_field": "id",
            "vector_field": "emb",
        },
        changeset_path=None,
    )
    assert source_type == "file"
    assert mapping["1"] == [0.1, 0.2]

    docs = [{"id": "1", "title": "a"}, {"id": "3", "title": "b"}]
    stats = augment_docs_with_embeddings(
        docs=docs,
        embedding_map=mapping,
        id_field="id",
        vector_field="emb",
    )
    assert stats == {"updated": 1, "missing": 1, "total": 2}
    assert docs[0]["emb"] == [0.1, 0.2]
