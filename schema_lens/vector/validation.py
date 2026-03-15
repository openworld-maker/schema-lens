"""Validation and embedding helpers for vector/hybrid simulation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.errors import ValidationError
from schema_lens.queries.model import QueryCase
from schema_lens.vector.model import VectorRuntimeConfig
from schema_lens.vector.query_builder import extract_query_vector

_ALLOWED_SIMILARITY = {"cosine", "dot", "euclidean"}


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float_list(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    out: list[float] = []
    for item in value:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            return None
    return out


def _resolve_path(base_path: Path | None, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if base_path is not None:
        candidate = (base_path.parent / path).resolve()
        if candidate.exists():
            return candidate
    return (Path.cwd() / path).resolve()


def _extract_field_def(schema: dict[str, Any], field_name: str) -> dict[str, Any] | None:
    fields = schema.get("schema", {}).get("fields", [])
    if not isinstance(fields, list):
        return None
    for field in fields:
        if isinstance(field, dict) and str(field.get("name")) == field_name:
            return field
    return None


def _extract_field_type(schema: dict[str, Any], type_name: str | None) -> dict[str, Any] | None:
    if not type_name:
        return None
    field_types = schema.get("schema", {}).get("fieldTypes", [])
    if not isinstance(field_types, list):
        return None
    for field_type in field_types:
        if isinstance(field_type, dict) and str(field_type.get("name")) == type_name:
            return field_type
    return None


def _detect_dimension(
    field_def: dict[str, Any] | None,
    field_type: dict[str, Any] | None,
) -> int | None:
    for payload in (field_def, field_type):
        if not isinstance(payload, dict):
            continue
        for key in ("vectorDimension", "dimension", "dims"):
            value = _as_int(payload.get(key))
            if value:
                return value
    return None


def _detect_similarity(
    field_def: dict[str, Any] | None,
    field_type: dict[str, Any] | None,
) -> str | None:
    for payload in (field_def, field_type):
        if not isinstance(payload, dict):
            continue
        value = payload.get("similarityFunction") or payload.get("similarity")
        if value is None:
            continue
        return str(value).lower()
    return None


def _summarize(findings: list[dict[str, Any]]) -> dict[str, int]:
    high = len([finding for finding in findings if finding.get("severity") == "HIGH"])
    medium = len([finding for finding in findings if finding.get("severity") == "MEDIUM"])
    low = len([finding for finding in findings if finding.get("severity") == "LOW"])
    return {
        "total": len(findings),
        "high": high,
        "medium": medium,
        "low": low,
    }


def validate_vector_setup(
    *,
    baseline_schema: dict[str, Any],
    vector_cfg: VectorRuntimeConfig,
    query_cases: list[QueryCase],
    vector_dimension_override: int | None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    field_def = _extract_field_def(baseline_schema, vector_cfg.field)
    field_type = _extract_field_type(
        baseline_schema,
        str(field_def.get("type")) if isinstance(field_def, dict) else None,
    )
    schema_dimension = _detect_dimension(field_def, field_type)
    schema_similarity = _detect_similarity(field_def, field_type)

    expected_dimension = vector_dimension_override or vector_cfg.dimension or schema_dimension

    if field_def is None:
        findings.append(
            {
                "code": "VECTOR_FIELD_NOT_FOUND",
                "severity": "HIGH",
                "message": f"Vector field '{vector_cfg.field}' not found in schema",
            }
        )

    if vector_cfg.similarity and vector_cfg.similarity not in _ALLOWED_SIMILARITY:
        findings.append(
            {
                "code": "VECTOR_SIMILARITY_UNSUPPORTED",
                "severity": "MEDIUM",
                "message": f"Unknown similarity '{vector_cfg.similarity}'",
            }
        )

    if vector_cfg.similarity and schema_similarity and vector_cfg.similarity != schema_similarity:
        findings.append(
            {
                "code": "VECTOR_SIMILARITY_MISMATCH",
                "severity": "MEDIUM",
                "message": (
                    f"Configured similarity '{vector_cfg.similarity}' differs from schema "
                    f"similarity '{schema_similarity}'"
                ),
                "schema_similarity": schema_similarity,
                "configured_similarity": vector_cfg.similarity,
            }
        )

    migration_required = False
    if vector_cfg.dimension and schema_dimension and vector_cfg.dimension != schema_dimension:
        migration_required = True
        findings.append(
            {
                "code": "VECTOR_DIMENSION_CHANGE_REQUIRES_MIGRATION",
                "severity": "HIGH",
                "message": (
                    f"Configured dimension {vector_cfg.dimension} differs from schema dimension "
                    f"{schema_dimension}; reindex with fresh embeddings is required"
                ),
                "schema_dimension": schema_dimension,
                "configured_dimension": vector_cfg.dimension,
            }
        )

    if expected_dimension is None:
        findings.append(
            {
                "code": "VECTOR_DIMENSION_UNKNOWN",
                "severity": "LOW",
                "message": "Vector dimension could not be resolved from config or schema",
            }
        )

    missing_vectors = 0
    dimension_mismatch = 0
    vectors_found = 0
    for case in query_cases:
        vector = extract_query_vector(case)
        if vector is None:
            missing_vectors += 1
            continue
        vectors_found += 1
        if expected_dimension is not None and len(vector) != expected_dimension:
            dimension_mismatch += 1
            findings.append(
                {
                    "code": "QUERY_VECTOR_DIMENSION_MISMATCH",
                    "severity": "HIGH",
                    "message": (
                        f"Query {case.id} vector dimension {len(vector)} does not match "
                        f"expected {expected_dimension}"
                    ),
                    "query_id": case.id,
                }
            )

    if missing_vectors > 0:
        severity = "MEDIUM" if vector_cfg.query_vector_policy == "fail" else "LOW"
        findings.append(
            {
                "code": "MISSING_QUERY_VECTORS",
                "severity": severity,
                "message": (
                    f"{missing_vectors} queries are missing vector payloads; policy is "
                    f"'{vector_cfg.query_vector_policy}'"
                ),
                "missing_queries": missing_vectors,
            }
        )

    block_run = False
    if any(
        finding.get("severity") == "HIGH"
        for finding in findings
        if finding.get("code") != "MISSING_QUERY_VECTORS"
    ):
        block_run = True
    if vector_cfg.query_vector_policy == "fail" and missing_vectors > 0:
        block_run = True

    return {
        "enabled": True,
        "field": vector_cfg.field,
        "expected_dimension": expected_dimension,
        "schema_dimension": schema_dimension,
        "schema_similarity": schema_similarity,
        "configured_similarity": vector_cfg.similarity,
        "query_vector_policy": vector_cfg.query_vector_policy,
        "migration_required": migration_required,
        "stats": {
            "queries_total": len(query_cases),
            "query_vectors_found": vectors_found,
            "missing_query_vectors": missing_vectors,
            "dimension_mismatch": dimension_mismatch,
        },
        "summary": _summarize(findings),
        "findings": findings,
        "block_run": block_run,
    }


def load_embeddings(
    *,
    embedding_source: dict[str, Any],
    changeset_path: Path | None,
) -> tuple[dict[str, list[float]], str]:
    source_type = str(embedding_source.get("type", "none"))
    if source_type == "none":
        return {}, source_type
    if source_type != "file":
        raise ValidationError(f"Unsupported vector embedding_source.type: {source_type}")

    raw_path = embedding_source.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValidationError("vector.embedding_source.path is required when type=file")
    path = _resolve_path(changeset_path, raw_path)
    if not path.exists():
        raise ValidationError(f"embedding source file not found: {path}")

    id_field = str(embedding_source.get("id_field", "id"))
    vector_field = str(embedding_source.get("vector_field", "emb"))
    mapping: dict[str, list[float]] = {}

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValidationError("embedding source JSON file must contain an array")
        rows = payload
    else:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    for row in rows:
        if not isinstance(row, dict):
            continue
        doc_id = row.get(id_field)
        if doc_id is None:
            continue
        vector = _safe_float_list(row.get(vector_field))
        if vector is None:
            continue
        mapping[str(doc_id)] = vector

    return mapping, source_type


def augment_docs_with_embeddings(
    *,
    docs: list[dict[str, Any]],
    embedding_map: dict[str, list[float]],
    id_field: str,
    vector_field: str,
) -> dict[str, int]:
    updated = 0
    missing = 0
    for doc in docs:
        doc_id = doc.get(id_field)
        if doc_id is None:
            continue
        vector = embedding_map.get(str(doc_id))
        if vector is None:
            missing += 1
            continue
        doc[vector_field] = vector
        updated += 1
    return {
        "updated": updated,
        "missing": missing,
        "total": len(docs),
    }
