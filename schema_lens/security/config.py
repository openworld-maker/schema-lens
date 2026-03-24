"""Security and audit configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditConfig:
    enabled: bool = False
    requested_by: str | None = None
    team: str | None = None
    ticket_id: str | None = None
    environment_label: str | None = None
    notes: str | None = None


@dataclass
class SecurityConfig:
    profile: str = "local-dev"
    redact_query_text: bool = False
    redact_doc_ids: bool = False
    hash_doc_ids: bool = False
    persist_raw_requests: bool = True
    persist_raw_docs: bool = True
    persist_debug_payloads: bool = True
    sensitive_fields: list[str] = field(default_factory=list)


def parse_security_config(raw: dict[str, Any] | None) -> SecurityConfig:
    payload = raw if isinstance(raw, dict) else {}
    fields = payload.get("sensitive_fields", [])
    return SecurityConfig(
        profile=str(payload.get("profile", "local-dev")),
        redact_query_text=bool(payload.get("redact_query_text", False)),
        redact_doc_ids=bool(payload.get("redact_doc_ids", False)),
        hash_doc_ids=bool(payload.get("hash_doc_ids", False)),
        persist_raw_requests=bool(payload.get("persist_raw_requests", True)),
        persist_raw_docs=bool(payload.get("persist_raw_docs", True)),
        persist_debug_payloads=bool(payload.get("persist_debug_payloads", True)),
        sensitive_fields=[str(item) for item in fields if isinstance(item, str)],
    )


def parse_audit_config(raw: dict[str, Any] | None) -> AuditConfig:
    payload = raw if isinstance(raw, dict) else {}
    return AuditConfig(
        enabled=bool(payload.get("enabled", False)),
        requested_by=str(payload.get("requested_by")) if payload.get("requested_by") is not None else None,
        team=str(payload.get("team")) if payload.get("team") is not None else None,
        ticket_id=str(payload.get("ticket_id")) if payload.get("ticket_id") is not None else None,
        environment_label=(
            str(payload.get("environment_label")) if payload.get("environment_label") is not None else None
        ),
        notes=str(payload.get("notes")) if payload.get("notes") is not None else None,
    )
