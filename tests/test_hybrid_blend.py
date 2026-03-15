from __future__ import annotations

from schema_lens.vector.blend import blend_rankings

LEXICAL = [
    {"id": "A", "score": 10.0, "rank": 1},
    {"id": "B", "score": 9.0, "rank": 2},
    {"id": "C", "score": 8.0, "rank": 3},
]

VECTOR = [
    {"id": "C", "score": 0.9, "rank": 1},
    {"id": "D", "score": 0.8, "rank": 2},
    {"id": "A", "score": 0.7, "rank": 3},
]


def test_linear_blend_prefers_lexical_with_higher_weight():
    rows = blend_rankings(
        lexical_docs=LEXICAL,
        vector_docs=VECTOR,
        method="linear",
        top_k=3,
        candidate_pool=10,
        weight_lexical=0.8,
        weight_vector=0.2,
        normalize="none",
        missing_vector_score=0.0,
        missing_lexical_score=0.0,
        rrf_k=60,
    )
    assert rows[0]["id"] == "A"


def test_normalize_linear_can_promote_vector_candidate():
    rows = blend_rankings(
        lexical_docs=LEXICAL,
        vector_docs=VECTOR,
        method="normalize_linear",
        top_k=3,
        candidate_pool=10,
        weight_lexical=0.2,
        weight_vector=0.8,
        normalize="minmax",
        missing_vector_score=0.0,
        missing_lexical_score=0.0,
        rrf_k=60,
    )
    assert rows[0]["id"] in {"C", "D"}


def test_rrf_blend_combines_rank_positions():
    rows = blend_rankings(
        lexical_docs=LEXICAL,
        vector_docs=VECTOR,
        method="rrf",
        top_k=4,
        candidate_pool=10,
        weight_lexical=0.5,
        weight_vector=0.5,
        normalize="none",
        missing_vector_score=0.0,
        missing_lexical_score=0.0,
        rrf_k=10,
    )
    ids = [row["id"] for row in rows]
    assert "A" in ids
    assert "C" in ids


def test_normalize_linear_keeps_single_doc_signal():
    rows = blend_rankings(
        lexical_docs=[{"id": "A", "score": 42.0, "rank": 1}],
        vector_docs=[
            {"id": "B", "score": 0.95, "rank": 1},
            {"id": "A", "score": 0.90, "rank": 2},
        ],
        method="normalize_linear",
        top_k=2,
        candidate_pool=10,
        weight_lexical=0.9,
        weight_vector=0.1,
        normalize="zscore",
        missing_vector_score=0.0,
        missing_lexical_score=0.0,
        rrf_k=60,
    )
    assert rows[0]["id"] == "A"
