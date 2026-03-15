"""Solr runtime and index metric collection."""

from __future__ import annotations

from typing import Any

from schema_lens.solr.admin_api import admin_mbeans, admin_metrics, luke_info

_CACHE_NAMES = ("filterCache", "queryResultCache", "documentCache", "fieldValueCache")


def _find_named_metrics(obj: Any, name: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        normalized = {str(k): v for k, v in obj.items()}
        if name in normalized and isinstance(normalized[name], dict):
            found.append(normalized[name])
        for key, value in normalized.items():
            if name.lower() in key.lower() and isinstance(value, dict):
                found.append(value)
            found.extend(_find_named_metrics(value, name))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_named_metrics(item, name))
    return found


def _extract_cache_stats(payload: dict[str, Any], names: list[str]) -> dict[str, dict[str, float]]:
    caches: dict[str, dict[str, float]] = {}
    for name in names:
        entries = _find_named_metrics(payload, name)
        merged = {"hits": 0.0, "inserts": 0.0, "evictions": 0.0, "hitratio": 0.0}
        for entry in entries:
            for src_key, dst_key in (
                ("lookups", "hits"),
                ("hits", "hits"),
                ("inserts", "inserts"),
                ("evictions", "evictions"),
                ("hitratio", "hitratio"),
                ("hitRatio", "hitratio"),
            ):
                value = entry.get(src_key)
                if isinstance(value, (int, float)):
                    merged[dst_key] += float(value)
        caches[name] = merged
    return caches


def _extract_index_stats(luke_payload: dict[str, Any]) -> dict[str, Any]:
    index = luke_payload.get("index", {}) if isinstance(luke_payload, dict) else {}
    if not isinstance(index, dict):
        index = {}
    return {
        "numDocs": index.get("numDocs"),
        "deletedDocs": index.get("deletedDocs"),
        "segmentCount": index.get("segmentCount"),
        "indexSizeBytes": index.get("sizeInBytes") or index.get("size"),
    }


def collect_solr_runtime_snapshot(
    *,
    client: Any,
    collection: str,
    cache_names: list[str] | None = None,
    include_luke: bool = True,
) -> dict[str, Any]:
    cache_names = cache_names or list(_CACHE_NAMES)
    metrics_payload: dict[str, Any] = {}
    mbeans_payload: dict[str, Any] = {}
    luke_payload: dict[str, Any] = {}
    errors: list[str] = []

    try:
        metrics_payload = admin_metrics(client)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"metrics:{exc}")

    if not metrics_payload:
        try:
            mbeans_payload = admin_mbeans(client)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"mbeans:{exc}")

    if include_luke:
        try:
            luke_payload = luke_info(client, collection)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"luke:{exc}")

    source = "metrics" if metrics_payload else "mbeans"
    raw_payload = metrics_payload or mbeans_payload
    caches = _extract_cache_stats(raw_payload, cache_names)
    index_stats = _extract_index_stats(luke_payload)

    return {
        "enabled": True,
        "source": source,
        "caches": caches,
        "index": index_stats,
        "errors": errors,
        "raw_metrics_present": bool(metrics_payload),
        "raw_mbeans_present": bool(mbeans_payload),
        "raw_luke_present": bool(luke_payload),
    }
