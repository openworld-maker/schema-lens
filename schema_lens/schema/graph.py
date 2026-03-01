"""Build a normalized dependency graph from Solr schema JSON."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SchemaGraph:
    fields: dict[str, str]
    dynamic_fields: dict[str, str]
    copy_fields: list[dict[str, Any]]
    field_type_to_fields: dict[str, list[str]]
    field_type_to_dynamic_fields: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": self.fields,
            "dynamic_fields": self.dynamic_fields,
            "copy_fields": self.copy_fields,
            "field_type_to_fields": self.field_type_to_fields,
            "field_type_to_dynamic_fields": self.field_type_to_dynamic_fields,
        }


def _schema_body(schema_json: dict[str, Any]) -> dict[str, Any]:
    return schema_json.get("schema", schema_json)


def build_schema_graph(schema_json: dict[str, Any]) -> SchemaGraph:
    body = _schema_body(schema_json)

    fields: dict[str, str] = {}
    for field in body.get("fields", []):
        name = field.get("name")
        field_type = field.get("type")
        if isinstance(name, str) and isinstance(field_type, str):
            fields[name] = field_type

    dynamic_fields: dict[str, str] = {}
    for field in body.get("dynamicFields", []):
        name = field.get("name")
        field_type = field.get("type")
        if isinstance(name, str) and isinstance(field_type, str):
            dynamic_fields[name] = field_type

    copy_fields: list[dict[str, Any]] = []
    for rule in body.get("copyFields", []):
        source = rule.get("source")
        dest = rule.get("dest")
        if not isinstance(source, str) or not isinstance(dest, str):
            continue
        out = {"source": source, "dest": dest}
        if "maxChars" in rule:
            out["maxChars"] = rule.get("maxChars")
        copy_fields.append(out)

    field_type_to_fields: dict[str, list[str]] = {}
    for name, field_type in fields.items():
        field_type_to_fields.setdefault(field_type, []).append(name)
    for _, names in field_type_to_fields.items():
        names.sort()

    field_type_to_dynamic_fields: dict[str, list[str]] = {}
    for pattern, field_type in dynamic_fields.items():
        field_type_to_dynamic_fields.setdefault(field_type, []).append(pattern)
    for _, names in field_type_to_dynamic_fields.items():
        names.sort()

    return SchemaGraph(
        fields=fields,
        dynamic_fields=dynamic_fields,
        copy_fields=copy_fields,
        field_type_to_fields=field_type_to_fields,
        field_type_to_dynamic_fields=field_type_to_dynamic_fields,
    )

