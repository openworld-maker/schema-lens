"""Typed models for Solr compatibility and capability detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VersionInfo:
    raw_version: str | None
    major: int | None
    minor: int | None
    patch: int | None
    deployment_mode: str
    node_name: str | None = None

    @property
    def version_string(self) -> str | None:
        if self.major is None or self.minor is None or self.patch is None:
            return self.raw_version
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["normalized_version"] = self.version_string
        return payload


@dataclass
class CapabilityRegistry:
    metrics_json_supported: bool = False
    metrics_mbeans_supported: bool = False
    metrics_prometheus_default_hint: bool = False
    configset_upload_supported: bool = False
    configset_download_supported: bool = False
    collections_api_supported: bool = False
    alias_ops_supported: bool = False
    luke_supported: bool = False
    structured_explain_supported: bool = False
    parsedquery_available: bool = False
    vector_supported: bool = False
    vector_native_hybrid_supported: bool = False
    json_request_supported: bool = False
    ltr_possible: bool = False
    feature_logging_possible: bool = False
    package_manager_possible: bool = False
    unsupported_reasons: dict[str, str] = field(default_factory=dict)
    degraded_modes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    probe_results: dict[str, bool] = field(default_factory=dict)

    def as_compat_flags(self, *, version_detected: bool, solr_major: int | None) -> dict[str, Any]:
        """Expose canonical and backward-compatible flags expected by existing runtime code."""
        payload = {
            "version_detected": version_detected,
            "solr_major": solr_major,
            "metrics_json_supported": self.metrics_json_supported,
            "metrics_mbeans_supported": self.metrics_mbeans_supported,
            "metrics_prometheus_default_hint": self.metrics_prometheus_default_hint,
            "configset_upload_supported": self.configset_upload_supported,
            "configset_download_supported": self.configset_download_supported,
            "collections_api_supported": self.collections_api_supported,
            "alias_ops_supported": self.alias_ops_supported,
            "luke_supported": self.luke_supported,
            "structured_explain_supported": self.structured_explain_supported,
            "parsedquery_available": self.parsedquery_available,
            "vector_supported": self.vector_supported,
            "vector_native_hybrid_supported": self.vector_native_hybrid_supported,
            "json_request_supported": self.json_request_supported,
            "ltr_possible": self.ltr_possible,
            "feature_logging_possible": self.feature_logging_possible,
            "package_manager_possible": self.package_manager_possible,
            "unsupported_reasons": dict(self.unsupported_reasons),
            "degraded_modes": list(self.degraded_modes),
            "warnings": list(self.warnings),
            "probe_results": dict(self.probe_results),
            # Legacy compatibility keys.
            "metrics_prometheus_default": self.metrics_prometheus_default_hint,
            "vector_query_supported": self.vector_supported,
            "package_manager_available": self.package_manager_possible,
            "ltr_available": self.ltr_possible,
            # Enterprise-facing contract aliases currently used in docs/reports.
            "collections_api": self.collections_api_supported,
            "schema_api": True,
            "config_api": True,
            "managed_resources": True,
            "vector_search": self.vector_supported,
            "ltr": self.ltr_possible,
            "aliases": self.alias_ops_supported,
            "metrics_api": self.metrics_json_supported or self.metrics_mbeans_supported,
            "security_api": True,
            "package_manager": self.package_manager_possible,
            "streaming_expressions": True,
            "v2_api": bool(solr_major is not None and solr_major >= 9),
        }
        return payload


@dataclass
class CompatibilityContract:
    version: VersionInfo
    capabilities: dict[str, Any]
    support_tier: str
    confidence: str
    missing_capabilities: list[str] = field(default_factory=list)
    disabled_features: list[str] = field(default_factory=list)
    fallbacks: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    degraded_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "solr_version": self.version.version_string,
            "version": self.version.to_dict(),
            "support_tier": self.support_tier,
            "confidence": self.confidence,
            "capabilities": self.capabilities,
            "missing_capabilities": list(self.missing_capabilities),
            "disabled_features": list(self.disabled_features),
            "fallbacks": list(self.fallbacks),
            "warnings": list(self.warnings),
            "degraded_modes": list(self.degraded_modes),
        }
