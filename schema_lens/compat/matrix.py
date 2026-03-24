"""Version-to-capability defaults for Solr compatibility detection."""

from __future__ import annotations

from schema_lens.compat.models import CapabilityRegistry


def defaults_for_major(major: int | None) -> CapabilityRegistry:
    """Return default capability assumptions for a Solr major version."""
    # Unknown version: conservative but still allow common baseline APIs.
    if major is None:
        return CapabilityRegistry(
            metrics_json_supported=True,
            metrics_mbeans_supported=True,
            configset_upload_supported=True,
            configset_download_supported=True,
            collections_api_supported=True,
            alias_ops_supported=True,
            luke_supported=True,
            structured_explain_supported=False,
            parsedquery_available=True,
            vector_supported=False,
            vector_native_hybrid_supported=False,
            json_request_supported=True,
            ltr_possible=True,
            feature_logging_possible=False,
            package_manager_possible=False,
            warnings=["Solr version could not be detected; using conservative compatibility defaults."],
        )

    # Solr 8.x
    if major <= 8:
        return CapabilityRegistry(
            metrics_json_supported=True,
            metrics_mbeans_supported=True,
            configset_upload_supported=True,
            configset_download_supported=True,
            collections_api_supported=True,
            alias_ops_supported=True,
            luke_supported=True,
            structured_explain_supported=False,
            parsedquery_available=True,
            vector_supported=False,
            vector_native_hybrid_supported=False,
            json_request_supported=True,
            ltr_possible=True,
            feature_logging_possible=True,
            package_manager_possible=False,
            degraded_modes=[
                "structured_explain_unavailable",
                "vector_features_unavailable",
                "package_manager_unavailable",
            ],
        )

    # Solr 9.x
    if major == 9:
        return CapabilityRegistry(
            metrics_json_supported=True,
            metrics_mbeans_supported=True,
            metrics_prometheus_default_hint=False,
            configset_upload_supported=True,
            configset_download_supported=True,
            collections_api_supported=True,
            alias_ops_supported=True,
            luke_supported=True,
            structured_explain_supported=True,
            parsedquery_available=True,
            vector_supported=True,
            vector_native_hybrid_supported=True,
            json_request_supported=True,
            ltr_possible=True,
            feature_logging_possible=True,
            package_manager_possible=True,
        )

    # Solr 10.x+ (forward-ready default assumptions)
    return CapabilityRegistry(
        metrics_json_supported=True,
        metrics_mbeans_supported=True,
        metrics_prometheus_default_hint=True,
        configset_upload_supported=True,
        configset_download_supported=True,
        collections_api_supported=True,
        alias_ops_supported=True,
        luke_supported=True,
        structured_explain_supported=True,
        parsedquery_available=True,
        vector_supported=True,
        vector_native_hybrid_supported=True,
        json_request_supported=True,
        ltr_possible=True,
        feature_logging_possible=True,
        package_manager_possible=True,
        warnings=["Solr 10+ detected; using forward-ready assumptions where runtime probes are unavailable."],
    )
