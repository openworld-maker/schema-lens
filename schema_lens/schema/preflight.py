"""Schema preflight risk checks for planned changes."""

from __future__ import annotations

from typing import Any

from schema_lens.schema.graph import SchemaGraph, build_schema_graph

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"


def _severity_rank(value: str) -> int:
    return {HIGH: 3, MEDIUM: 2, LOW: 1}.get(value, 0)


def _type_for_endpoint(graph: SchemaGraph, endpoint: str) -> tuple[str | None, str]:
    if endpoint in graph.fields:
        return graph.fields[endpoint], "field"
    if endpoint in graph.dynamic_fields:
        return graph.dynamic_fields[endpoint], "dynamicField"
    if "*" in endpoint:
        return graph.dynamic_fields.get(endpoint), "dynamicFieldPattern"
    return None, "unknown"


def _add_finding(
    findings: list[dict[str, Any]],
    *,
    code: str,
    severity: str,
    op_index: int,
    message: str,
    impacted_fields: list[str] | None = None,
    impacted_dynamic_fields: list[str] | None = None,
    copyfields: list[dict[str, Any]] | None = None,
    recommendation: str | None = None,
) -> None:
    findings.append(
        {
            "code": code,
            "severity": severity,
            "op_index": op_index,
            "message": message,
            "impacted_fields": impacted_fields or [],
            "impacted_dynamic_fields": impacted_dynamic_fields or [],
            "copyfields": copyfields or [],
            "recommendation": recommendation
            or "Review affected schema elements and apply changes in a safe order.",
        }
    )


def _field_update_type_change(
    graph: SchemaGraph,
    op: dict[str, Any],
) -> tuple[str | None, str | None]:
    field = op.get("field")
    if not isinstance(field, str):
        return None, None
    old_type = graph.fields.get(field)
    new_type = op.get("set", {}).get("type") if isinstance(op.get("set"), dict) else None
    if not isinstance(new_type, str) or new_type == old_type:
        return None, None
    return old_type, new_type


def run_preflight(
    schema_json: dict[str, Any],
    changes: list[dict[str, Any]],
    *,
    fail_on_risk: bool = False,
) -> dict[str, Any]:
    graph = build_schema_graph(schema_json)
    findings: list[dict[str, Any]] = []

    for idx, op in enumerate(changes):
        op_name = op.get("op")
        touched_types: set[str] = set()
        touched_fields: set[str] = set()

        if op_name == "schema.fieldType.replace":
            src = op.get("name")
            dst = op.get("with")
            if isinstance(src, str):
                touched_types.add(src)
            if isinstance(dst, str):
                touched_types.add(dst)
        elif op_name == "schema.analyzer.remove_filter":
            field_type = op.get("fieldType")
            if isinstance(field_type, str):
                touched_types.add(field_type)
        elif op_name == "schema.field.update":
            field = op.get("field")
            if isinstance(field, str):
                touched_fields.add(field)
            old_type, new_type = _field_update_type_change(graph, op)
            if old_type:
                touched_types.add(old_type)
            if new_type:
                touched_types.add(new_type)

        for field_type in sorted(touched_types):
            impacted_fields = graph.field_type_to_fields.get(field_type, [])
            impacted_dynamic = graph.field_type_to_dynamic_fields.get(field_type, [])
            if impacted_fields or impacted_dynamic:
                _add_finding(
                    findings,
                    code="FIELDTYPE_IMPACT",
                    severity=LOW,
                    op_index=idx,
                    message=(
                        f"Change touches fieldType '{field_type}' used by "
                        f"{len(impacted_fields)} fields and {len(impacted_dynamic)} dynamic fields."
                    ),
                    impacted_fields=impacted_fields,
                    impacted_dynamic_fields=impacted_dynamic,
                    recommendation=(
                        "Verify analyzer/tokenization compatibility and reindex "
                        "expectations for all impacted fields."
                    ),
                )

        risky_copyfields: list[dict[str, Any]] = []
        known_hazard_copyfields: list[dict[str, Any]] = []
        for rule in graph.copy_fields:
            src = str(rule.get("source"))
            dst = str(rule.get("dest"))
            src_type, src_kind = _type_for_endpoint(graph, src)
            dst_type, dst_kind = _type_for_endpoint(graph, dst)

            type_touched = (src_type in touched_types) or (dst_type in touched_types)
            field_touched = src in touched_fields or dst in touched_fields
            if type_touched or field_touched:
                risky_copyfields.append(
                    {
                        **rule,
                        "source_kind": src_kind,
                        "dest_kind": dst_kind,
                        "source_type": src_type,
                        "dest_type": dst_type,
                    }
                )

            if (
                op_name == "schema.fieldType.replace"
                and dst_kind == "field"
                and dst_type in touched_types
            ):
                known_hazard_copyfields.append(
                    {
                        **rule,
                        "source_kind": src_kind,
                        "dest_kind": dst_kind,
                        "source_type": src_type,
                        "dest_type": dst_type,
                    }
                )

        if risky_copyfields:
            _add_finding(
                findings,
                code="COPYFIELD_COMPAT_RISK",
                severity=MEDIUM,
                op_index=idx,
                message=(
                    "Change intersects copyField dependencies; validate "
                    "source/destination compatibility."
                ),
                impacted_fields=sorted(touched_fields),
                copyfields=risky_copyfields,
                recommendation=(
                    "Validate copyField sources/destinations after schema change "
                    "and ensure destination field semantics remain valid."
                ),
            )
        if known_hazard_copyfields:
            _add_finding(
                findings,
                code="REPLACE_FIELDTYPE_COPYFIELD_DEST_HAZARD",
                severity=HIGH,
                op_index=idx,
                message=(
                    "Potential replace-field-type/copyField destination hazard "
                    "detected on concrete destination fields."
                ),
                impacted_fields=sorted(touched_fields),
                copyfields=known_hazard_copyfields,
                recommendation=(
                    "Apply field/copyField updates in controlled order and validate "
                    "replace-field-type compatibility before execution."
                ),
            )

    summary = {
        "total": len(findings),
        "high": len([f for f in findings if f.get("severity") == HIGH]),
        "medium": len([f for f in findings if f.get("severity") == MEDIUM]),
        "low": len([f for f in findings if f.get("severity") == LOW]),
        "max_severity": "NONE",
    }
    if findings:
        summary["max_severity"] = max(
            (str(f.get("severity", LOW)) for f in findings),
            key=_severity_rank,
        )

    block_run = bool(fail_on_risk and summary["high"] > 0)

    return {
        "summary": summary,
        "block_run": block_run,
        "fail_on_risk": bool(fail_on_risk),
        "findings": findings,
        "graph": graph.to_dict(),
    }
