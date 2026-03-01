"""Schema operation application logic."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from schema_lens.errors import ValidationError


def _schema_body(schema_json: dict[str, Any]) -> dict[str, Any]:
    return schema_json.get("schema", schema_json)


def _find_field(schema_json: dict[str, Any], field_name: str) -> dict[str, Any] | None:
    fields = _schema_body(schema_json).get("fields", [])
    for field in fields:
        if field.get("name") == field_name:
            return field
    return None


def _field_types(schema_json: dict[str, Any]) -> list[dict[str, Any]]:
    return _schema_body(schema_json).get("fieldTypes", [])


def _find_field_type(schema_json: dict[str, Any], type_name: str) -> dict[str, Any] | None:
    for field_type in _field_types(schema_json):
        if field_type.get("name") == type_name:
            return field_type
    return None


def _all_fields_with_type(schema_json: dict[str, Any], type_name: str) -> list[dict[str, Any]]:
    fields = _schema_body(schema_json).get("fields", [])
    return [field for field in fields if field.get("type") == type_name]


def prepare_field_update(schema_json: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    field = op["field"]
    base = _find_field(schema_json, field)
    if base is None:
        raise ValidationError(f"Field not found in baseline schema: {field}")
    merged = deepcopy(base)
    merged.update(op.get("set", {}))
    merged["name"] = field
    return merged


def prepare_field_type_replace_updates(
    schema_json: dict[str, Any], op: dict[str, Any]
) -> list[dict[str, Any]]:
    src = op["name"]
    dst = op["with"]
    fields = _all_fields_with_type(schema_json, src)
    replacements: list[dict[str, Any]] = []
    for field in fields:
        upd = deepcopy(field)
        upd["type"] = dst
        replacements.append(upd)
    return replacements


def _remove_matching_filters(
    analyzer_block: dict[str, Any], filter_class: str
) -> tuple[dict[str, Any], int]:
    def normalize(value: str | None) -> str:
        if not value:
            return ""
        out = value
        out = out.replace("solr.", "")
        out = out.replace("FilterFactory", "")
        out = re.sub(r"[^a-zA-Z0-9]+", "", out)
        return out.lower()

    target_norm = normalize(filter_class)

    def matches(filter_def: dict[str, Any]) -> bool:
        candidates = [
            filter_def.get("class"),
            filter_def.get("name"),
        ]
        for candidate in candidates:
            if candidate == filter_class:
                return True
            if normalize(candidate) == target_norm:
                return True
        return False

    updated = deepcopy(analyzer_block)
    removed = 0

    if "filters" in updated and isinstance(updated["filters"], list):
        original = updated["filters"]
        filtered = [f for f in original if not matches(f)]
        removed = len(original) - len(filtered)
        updated["filters"] = filtered
        return updated, removed

    if "filter" in updated:
        filter_val = updated["filter"]
        if isinstance(filter_val, list):
            original = filter_val
            filtered = [f for f in original if not matches(f)]
            removed = len(original) - len(filtered)
            updated["filter"] = filtered
        elif isinstance(filter_val, dict):
            if matches(filter_val):
                updated["filter"] = []
                removed = 1
        return updated, removed

    return updated, 0


def prepare_remove_filter_field_type(
    schema_json: dict[str, Any], op: dict[str, Any]
) -> dict[str, Any]:
    field_type_name = op["fieldType"]
    analyzer_name = op["analyzer"]
    filter_class = op["filter_class"]

    field_type = _find_field_type(schema_json, field_type_name)
    if field_type is None:
        raise ValidationError(f"FieldType not found in baseline schema: {field_type_name}")

    updated_ft = deepcopy(field_type)

    analyzer_key = None
    if analyzer_name == "index":
        if "indexAnalyzer" in updated_ft:
            analyzer_key = "indexAnalyzer"
        elif "analyzer" in updated_ft:
            analyzer_key = "analyzer"
    elif analyzer_name == "query":
        if "queryAnalyzer" in updated_ft:
            analyzer_key = "queryAnalyzer"
        elif "analyzer" in updated_ft:
            analyzer_key = "analyzer"

    if analyzer_key is None:
        raise ValidationError(
            f"FieldType {field_type_name} does not expose analyzer block for '{analyzer_name}'"
        )

    updated_analyzer, removed = _remove_matching_filters(updated_ft[analyzer_key], filter_class)
    if removed == 0:
        raise ValidationError(
            f"No filter with class {filter_class} found in {field_type_name}.{analyzer_key}"
        )

    updated_ft[analyzer_key] = updated_analyzer
    return updated_ft


def apply_schema_operations(
    client: Any,
    shadow_collection: str,
    baseline_schema: dict[str, Any],
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from schema_lens.solr import schema_api

    applied: list[dict[str, Any]] = []

    for op in changes:
        op_name = op.get("op")
        if op_name == "schema.field.update":
            payload = prepare_field_update(baseline_schema, op)
            schema_api.replace_field(client, shadow_collection, payload)
            applied.append({"op": op_name, "field": payload.get("name")})

        elif op_name == "schema.fieldType.replace":
            updates = prepare_field_type_replace_updates(baseline_schema, op)
            for payload in updates:
                schema_api.replace_field(client, shadow_collection, payload)
            applied.append(
                {
                    "op": op_name,
                    "from": op.get("name"),
                    "to": op.get("with"),
                    "fields": len(updates),
                }
            )

        elif op_name == "schema.analyzer.remove_filter":
            try:
                payload = prepare_remove_filter_field_type(baseline_schema, op)
            except ValidationError as exc:
                # Make remove-filter idempotent for repeated runs.
                if "No filter with class" in str(exc):
                    applied.append(
                        {
                            "op": op_name,
                            "fieldType": op.get("fieldType"),
                            "analyzer": op.get("analyzer"),
                            "filter_class": op.get("filter_class"),
                            "skipped": True,
                            "warning": str(exc),
                        }
                    )
                    continue
                raise
            schema_api.replace_field_type(client, shadow_collection, payload)
            applied.append(
                {
                    "op": op_name,
                    "fieldType": op.get("fieldType"),
                    "analyzer": op.get("analyzer"),
                    "filter_class": op.get("filter_class"),
                }
            )

    return applied
