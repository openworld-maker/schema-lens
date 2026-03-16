"""Solr compatibility detection and adapters."""

from schema_lens.compat.capabilities import capabilities_for_version
from schema_lens.compat.capabilities import compatibility_contract
from schema_lens.compat.detect import detect_solr_version

__all__ = ["detect_solr_version", "capabilities_for_version", "compatibility_contract"]
