"""Capability registry keyed by detected Solr version."""

from __future__ import annotations

from typing import Any

from schema_lens.compat.detect import parse_major


DEFAULT_CAPABILITIES = {
    # Existing flags used by runtime adapters.
    "metrics_json_supported": True,
    "metrics_prometheus_default": False,
    "vector_query_supported": False,
    "configset_upload_supported": True,
    "structured_explain_supported": False,
    "ltr_available": True,
    "package_manager_available": False,
    # Enterprise-facing contract flags.
    "collections_api": True,
    "schema_api": True,
    "config_api": True,
    "managed_resources": True,
    "vector_search": False,
    "ltr": True,
    "aliases": True,
    "metrics_api": True,
    "security_api": True,
    "package_manager": False,
    "streaming_expressions": True,
    "v2_api": False,
}


def capabilities_for_version(version: str | None) -> dict[str, Any]:
    caps = dict(DEFAULT_CAPABILITIES)
    major = parse_major(version)

    if major is None:
        caps["version_detected"] = False
        return caps

    caps["version_detected"] = True
    caps["solr_major"] = major

    if major >= 9:
        caps["vector_query_supported"] = True
        caps["structured_explain_supported"] = True
        caps["package_manager_available"] = True
        caps["vector_search"] = True
        caps["package_manager"] = True
        caps["v2_api"] = True

    if major >= 10:
        caps["metrics_prometheus_default"] = True

    return caps


def compatibility_contract(version: str | None) -> dict[str, Any]:
    """Return report-ready compatibility metadata with deterministic fallbacks."""
    caps = capabilities_for_version(version)
    expected = {
        "collections_api",
        "schema_api",
        "config_api",
        "managed_resources",
        "vector_search",
        "ltr",
        "aliases",
        "metrics_api",
        "security_api",
        "package_manager",
        "streaming_expressions",
        "v2_api",
    }
    missing = sorted(key for key in expected if caps.get(key) is False)
    major = parse_major(version)
    if major is None:
        support_tier = "unknown"
        confidence = "low"
    elif major >= 10:
        support_tier = "forward_ready"
        confidence = "medium"
    elif major >= 9:
        support_tier = "recommended"
        confidence = "high"
    elif major >= 8:
        support_tier = "supported_with_fallbacks"
        confidence = "high"
    else:
        support_tier = "unknown"
        confidence = "low"

    fallbacks: list[dict[str, str]] = []
    if caps.get("vector_search") is False:
        fallbacks.append({"feature": "vector_hybrid", "fallback": "skip_vector_track"})
    if caps.get("v2_api") is False:
        fallbacks.append({"feature": "v2_api", "fallback": "v1_admin_endpoints"})
    if caps.get("package_manager") is False:
        fallbacks.append({"feature": "package_manager", "fallback": "manual_plugin_deploy"})

    return {
        "solr_version": version,
        "support_tier": support_tier,
        "confidence": confidence,
        "capabilities": caps,
        "missing_capabilities": missing,
        "fallbacks": fallbacks,
    }
