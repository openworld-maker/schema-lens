"""Solr compatibility detection and adapters."""

from schema_lens.compat.capabilities import capabilities_for_version, compatibility_contract, detect_capability_registry
from schema_lens.compat.detect import detect_solr_version, detect_version_info, probe_runtime_capabilities
from schema_lens.compat.models import CapabilityRegistry, CompatibilityContract, VersionInfo

__all__ = [
    "detect_solr_version",
    "detect_version_info",
    "probe_runtime_capabilities",
    "capabilities_for_version",
    "detect_capability_registry",
    "compatibility_contract",
    "VersionInfo",
    "CapabilityRegistry",
    "CompatibilityContract",
]
