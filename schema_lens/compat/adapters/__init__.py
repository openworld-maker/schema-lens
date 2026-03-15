"""Compatibility adapters for optional feature tracks."""

from schema_lens.compat.adapters.configset import configset_upload_supported
from schema_lens.compat.adapters.explain import structured_explain_supported
from schema_lens.compat.adapters.metrics import metrics_supported
from schema_lens.compat.adapters.vector import vector_supported

__all__ = [
    "metrics_supported",
    "vector_supported",
    "structured_explain_supported",
    "configset_upload_supported",
]
