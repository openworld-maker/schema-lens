"""Capability registry and compatibility contract builders."""

from __future__ import annotations

from typing import Any

from schema_lens.compat.detect import detect_version_info, parse_major
from schema_lens.compat.matrix import defaults_for_major
from schema_lens.compat.models import CapabilityRegistry, CompatibilityContract, VersionInfo

_CANONICAL_KEYS = {
    "metrics_json_supported",
    "metrics_mbeans_supported",
    "metrics_prometheus_default_hint",
    "configset_upload_supported",
    "configset_download_supported",
    "collections_api_supported",
    "alias_ops_supported",
    "luke_supported",
    "structured_explain_supported",
    "parsedquery_available",
    "vector_supported",
    "vector_native_hybrid_supported",
    "json_request_supported",
    "ltr_possible",
    "feature_logging_possible",
    "package_manager_possible",
}


def _infer_tier(major: int | None) -> tuple[str, str]:
    if major is None:
        return "unknown", "low"
    if major >= 10:
        return "forward_ready", "medium"
    if major >= 9:
        return "recommended", "high"
    if major >= 8:
        return "supported_with_fallbacks", "high"
    return "unknown", "low"


def _merge_probe_overrides(registry: CapabilityRegistry, probe_results: dict[str, bool] | None) -> None:
    if not isinstance(probe_results, dict):
        return

    registry.probe_results.update({str(k): bool(v) for k, v in probe_results.items()})

    def _apply(attr: str, probe_key: str, reason: str) -> None:
        value = probe_results.get(probe_key)
        if value is None:
            return
        if bool(value):
            setattr(registry, attr, True)
            return
        setattr(registry, attr, False)
        registry.unsupported_reasons[attr] = reason

    _apply("metrics_json_supported", "metrics_json", "Runtime probe for /admin/metrics failed")
    _apply("metrics_mbeans_supported", "metrics_mbeans", "Runtime probe for /admin/mbeans failed")
    _apply("collections_api_supported", "collections_api", "Collections API probe failed")
    _apply("alias_ops_supported", "alias_ops", "Alias operations probe failed")
    _apply("configset_upload_supported", "configset_list", "Configset LIST probe failed")
    _apply("configset_download_supported", "configset_list", "Configset LIST probe failed")
    _apply("luke_supported", "luke", "Luke endpoint probe failed")
    _apply("json_request_supported", "json_query", "JSON request endpoint probe failed")
    _apply(
        "structured_explain_supported",
        "structured_explain",
        "Structured explain probe failed; falling back to classic explain",
    )


def _resolve_version_info(
    version_or_info: str | VersionInfo | None,
    system_info: dict[str, Any] | None,
) -> VersionInfo:
    if isinstance(version_or_info, VersionInfo):
        return version_or_info
    if isinstance(system_info, dict):
        info = detect_version_info(system_info)
        if info.version_string is not None:
            return info
    major = parse_major(version_or_info)
    if major is None:
        return VersionInfo(raw_version=None, major=None, minor=None, patch=None, deployment_mode="unknown")
    parts = str(version_or_info).split(".")
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return VersionInfo(
        raw_version=f"{major}.{minor}.{patch}",
        major=major,
        minor=minor,
        patch=patch,
        deployment_mode="unknown",
    )


def capabilities_for_version(
    version: str | None,
    *,
    probe_results: dict[str, bool] | None = None,
) -> dict[str, Any]:
    major = parse_major(version)
    registry = defaults_for_major(major)
    _merge_probe_overrides(registry, probe_results)
    return registry.as_compat_flags(version_detected=major is not None, solr_major=major)


def detect_capability_registry(
    *,
    version_or_info: str | VersionInfo | None,
    system_info: dict[str, Any] | None = None,
    probe_results: dict[str, bool] | None = None,
) -> tuple[VersionInfo, dict[str, Any], CapabilityRegistry]:
    version_info = _resolve_version_info(version_or_info, system_info)
    registry = defaults_for_major(version_info.major)
    _merge_probe_overrides(registry, probe_results)
    caps = registry.as_compat_flags(
        version_detected=version_info.major is not None,
        solr_major=version_info.major,
    )

    # Preserve deterministic SolrCloud hints when version probe had partial context.
    if version_info.deployment_mode == "solrcloud":
        caps.setdefault("collections_api_supported", True)
        caps.setdefault("alias_ops_supported", True)

    return version_info, caps, registry


def _fallbacks_from_caps(caps: dict[str, Any]) -> tuple[list[dict[str, str]], list[str], list[str]]:
    fallbacks: list[dict[str, str]] = []
    disabled: list[str] = []
    warnings: list[str] = []

    if not bool(caps.get("vector_supported", False)):
        disabled.append("vector_hybrid")
        fallbacks.append(
            {
                "feature": "vector_hybrid",
                "fallback": "disable_vector_scenarios",
                "reason": "Vector capability unavailable on target Solr",
            }
        )
    elif not bool(caps.get("vector_native_hybrid_supported", False)):
        fallbacks.append(
            {
                "feature": "vector_hybrid",
                "fallback": "client_side_hybrid_simulation",
                "reason": "Native hybrid vector support unavailable",
            }
        )

    if not bool(caps.get("structured_explain_supported", False)):
        disabled.append("structured_explain")
        fallbacks.append(
            {
                "feature": "structured_explain",
                "fallback": "raw_explain_output",
                "reason": "Structured explain API unavailable",
            }
        )

    if not bool(caps.get("metrics_json_supported", False)) and bool(caps.get("metrics_mbeans_supported", False)):
        fallbacks.append(
            {
                "feature": "metrics_capture",
                "fallback": "admin_mbeans",
                "reason": "Using /admin/mbeans fallback because /admin/metrics was unavailable",
            }
        )
    elif not bool(caps.get("metrics_json_supported", False)) and not bool(caps.get("metrics_mbeans_supported", False)):
        disabled.append("metrics_capture")
        warnings.append("Metrics endpoints unavailable; performance capture is degraded.")

    if not bool(caps.get("configset_upload_supported", False)):
        disabled.append("configset_upload")
        fallbacks.append(
            {
                "feature": "configset_upload",
                "fallback": "local_configset_directory",
                "reason": "Configset upload API unavailable",
            }
        )

    if not bool(caps.get("luke_supported", False)):
        disabled.append("index_luke_inspection")
        fallbacks.append(
            {
                "feature": "index_inspection",
                "fallback": "skip_luke_stats",
                "reason": "Luke endpoint unavailable",
            }
        )

    if not bool(caps.get("ltr_possible", False)):
        disabled.append("ltr_impact")
        warnings.append("LTR capability unavailable; LTR impact analysis is disabled.")

    return fallbacks, disabled, warnings


def compatibility_contract(
    version_or_info: str | VersionInfo | None,
    *,
    system_info: dict[str, Any] | None = None,
    probe_results: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Return report-ready compatibility metadata with deterministic fallbacks."""

    version_info, caps, registry = detect_capability_registry(
        version_or_info=version_or_info,
        system_info=system_info,
        probe_results=probe_results,
    )
    support_tier, confidence = _infer_tier(version_info.major)

    missing = sorted(key for key, value in caps.items() if key in _CANONICAL_KEYS and value is False)
    fallbacks, disabled, warnings = _fallbacks_from_caps(caps)

    contract = CompatibilityContract(
        version=version_info,
        capabilities=caps,
        support_tier=support_tier,
        confidence=confidence,
        missing_capabilities=missing,
        disabled_features=disabled,
        fallbacks=fallbacks,
        warnings=list(dict.fromkeys([*registry.warnings, *warnings])),
        degraded_modes=list(dict.fromkeys(registry.degraded_modes)),
    )
    return contract.to_dict()
