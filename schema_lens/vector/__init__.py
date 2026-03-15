"""Vector and hybrid simulation helpers."""

from schema_lens.vector.compare import compare_vector_hybrid
from schema_lens.vector.replay import run_vector_scenarios
from schema_lens.vector.scenario_parser import parse_vector_runtime_config
from schema_lens.vector.sensitivity import run_hybrid_sensitivity
from schema_lens.vector.validation import (
    augment_docs_with_embeddings,
    load_embeddings,
    validate_vector_setup,
)

__all__ = [
    "augment_docs_with_embeddings",
    "compare_vector_hybrid",
    "load_embeddings",
    "parse_vector_runtime_config",
    "run_hybrid_sensitivity",
    "run_vector_scenarios",
    "validate_vector_setup",
]
