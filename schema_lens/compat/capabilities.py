"""Capability registry keyed by detected Solr version."""

from __future__ import annotations

from typing import Any

from schema_lens.compat.detect import parse_major


DEFAULT_CAPABILITIES = {
    "metrics_json_supported": True,
    "metrics_prometheus_default": False,
    "vector_query_supported": False,
    "configset_upload_supported": True,
    "structured_explain_supported": False,
    "ltr_available": True,
    "package_manager_available": False,
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

    if major >= 10:
        caps["metrics_prometheus_default"] = True

    return caps
