"""Compatibility adapters for optional feature tracks."""

from schema_lens.compat.adapters.collections import alias_ops_supported, collections_api_supported
from schema_lens.compat.adapters.configset import configset_download_supported, configset_upload_supported
from schema_lens.compat.adapters.explain import extract_explain_debug, structured_explain_supported
from schema_lens.compat.adapters.ltr import feature_logging_supported, ltr_supported
from schema_lens.compat.adapters.metrics import metrics_supported, normalize_metrics_payload, preferred_metrics_source
from schema_lens.compat.adapters.vector import hybrid_mode, vector_runtime_message, vector_supported

__all__ = [
    "metrics_supported",
    "preferred_metrics_source",
    "normalize_metrics_payload",
    "vector_supported",
    "hybrid_mode",
    "vector_runtime_message",
    "structured_explain_supported",
    "extract_explain_debug",
    "configset_upload_supported",
    "configset_download_supported",
    "collections_api_supported",
    "alias_ops_supported",
    "ltr_supported",
    "feature_logging_supported",
]
