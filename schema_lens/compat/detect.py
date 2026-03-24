"""Solr version and capability probe helpers."""

from __future__ import annotations

import re
from typing import Any

from schema_lens.compat.models import VersionInfo
from schema_lens.errors import SolrRequestError

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def parse_major(version: str | None) -> int | None:
    if not isinstance(version, str) or not version:
        return None
    try:
        return int(version.split(".", 1)[0])
    except ValueError:
        return None


def _parse_version_parts(value: str | None) -> tuple[int | None, int | None, int | None, str | None]:
    if not isinstance(value, str):
        return None, None, None, None
    match = _VERSION_RE.search(value)
    if not match:
        return None, None, None, None
    major, minor, patch = match.groups()
    parsed = f"{int(major)}.{int(minor)}.{int(patch or 0)}"
    return int(major), int(minor), int(patch or 0), parsed


def detect_deployment_mode(system_info: dict[str, Any]) -> str:
    if not isinstance(system_info, dict):
        return "unknown"

    mode_value = system_info.get("mode")
    if isinstance(mode_value, str) and mode_value.strip():
        mode = mode_value.strip().lower()
        if mode in {"solrcloud", "cloud"}:
            return "solrcloud"
        if mode in {"standalone", "std", "single"}:
            return "standalone"

    if "zkHost" in system_info or "zk_host" in system_info:
        return "solrcloud"

    cloud = system_info.get("cloud")
    if isinstance(cloud, dict) and cloud:
        return "solrcloud"

    return "standalone"


def detect_version_info(system_info: dict[str, Any]) -> VersionInfo:
    lucene = system_info.get("lucene", {}) if isinstance(system_info, dict) else {}
    candidates = [
        lucene.get("solr-spec-version"),
        lucene.get("solr-impl-version"),
        system_info.get("solr-spec-version") if isinstance(system_info, dict) else None,
        system_info.get("solr_version") if isinstance(system_info, dict) else None,
    ]

    major: int | None = None
    minor: int | None = None
    patch: int | None = None
    raw: str | None = None

    for value in candidates:
        p_major, p_minor, p_patch, parsed = _parse_version_parts(value)
        if parsed is None:
            continue
        major, minor, patch = p_major, p_minor, p_patch
        raw = parsed
        break

    node_name = None
    if isinstance(system_info, dict):
        node_name_value = system_info.get("node") or system_info.get("host")
        if isinstance(node_name_value, str) and node_name_value.strip():
            node_name = node_name_value.strip()

    return VersionInfo(
        raw_version=raw,
        major=major,
        minor=minor,
        patch=patch,
        deployment_mode=detect_deployment_mode(system_info),
        node_name=node_name,
    )


def detect_solr_version(system_info: dict[str, Any]) -> str | None:
    """Backward-compatible helper that returns normalized version string only."""
    return detect_version_info(system_info).version_string


def probe_runtime_capabilities(
    *,
    client: Any,
    collection: str | None = None,
) -> dict[str, bool]:
    """Probe low-cost admin/query endpoints to confirm runtime capabilities."""

    def _ok(path: str, params: dict[str, Any] | None = None) -> bool:
        try:
            client.get_json(path, params=params or {"wt": "json"})
            return True
        except (SolrRequestError, Exception):  # noqa: BLE001
            return False

    results: dict[str, bool] = {
        "metrics_json": _ok("admin/metrics"),
        "metrics_mbeans": _ok("admin/mbeans", {"wt": "json", "stats": "true"}),
        "collections_api": _ok("admin/collections", {"wt": "json", "action": "CLUSTERSTATUS"}),
        "alias_ops": _ok("admin/collections", {"wt": "json", "action": "LISTALIASES"}),
        "configset_list": _ok("admin/configs", {"wt": "json", "action": "LIST"}),
    }

    if collection:
        results["luke"] = _ok(f"{collection}/admin/luke", {"wt": "json", "numTerms": "0"})
        results["json_query"] = _ok(f"{collection}/query", {"wt": "json", "rows": "0"})
        results["structured_explain"] = _ok(
            f"{collection}/select",
            {"wt": "json", "q": "*:*", "rows": "0", "debugQuery": "on", "debug.explain.structured": "true"},
        )
    else:
        results["luke"] = False
        results["json_query"] = False
        results["structured_explain"] = False

    return results
