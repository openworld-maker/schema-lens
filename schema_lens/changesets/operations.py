"""Supported changeset operations."""

from __future__ import annotations

SUPPORTED_OPS = {
    "schema.field.update",
    "schema.fieldType.replace",
    "schema.analyzer.remove_filter",
    "schema.synonym.update",
    "schema.stopwords.update",
    "queryparams.set",
}

SCHEMA_OPS = {
    "schema.field.update",
    "schema.fieldType.replace",
    "schema.analyzer.remove_filter",
}

CONFIGSET_OPS = {
    "schema.synonym.update",
    "schema.stopwords.update",
}
