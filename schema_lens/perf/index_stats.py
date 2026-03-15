"""Index and schema heuristics for cost impact."""

from __future__ import annotations

from typing import Any


def detect_schema_storage_impacts(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for op in changes:
        if not isinstance(op, dict):
            continue
        if op.get("op") != "schema.field.update":
            continue
        field = op.get("field")
        updates = op.get("set", {})
        if not isinstance(updates, dict):
            continue
        if "stored" in updates:
            findings.append(
                {
                    "field": field,
                    "kind": "stored",
                    "value": bool(updates.get("stored")),
                    "impact": "storage_footprint",
                }
            )
        if "docValues" in updates:
            findings.append(
                {
                    "field": field,
                    "kind": "docValues",
                    "value": bool(updates.get("docValues")),
                    "impact": "facet_sort_tradeoff",
                }
            )
    return findings


def compute_index_delta(
    baseline_index: dict[str, Any],
    shadow_index: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("numDocs", "deletedDocs", "segmentCount", "indexSizeBytes"):
        base = baseline_index.get(key)
        shadow = shadow_index.get(key)
        if isinstance(base, (int, float)) and isinstance(shadow, (int, float)):
            out[key] = {
                "baseline": base,
                "shadow": shadow,
                "delta": shadow - base,
                "delta_pct": ((shadow - base) / base * 100.0) if base else None,
            }
    return out
