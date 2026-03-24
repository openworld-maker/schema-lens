"""Security primitives for SolrGuard enterprise mode."""

from schema_lens.security.audit import build_audit_record
from schema_lens.security.auth import AuthMaterial, AuthResolutionError, resolve_auth_material
from schema_lens.security.config import AuditConfig, SecurityConfig, parse_audit_config, parse_security_config
from schema_lens.security.errors import AuthProviderError, SecretResolutionError, SecurityConfigError
from schema_lens.security.profiles import SecurityProfile, resolve_profile
from schema_lens.security.redaction import (
    REDACTED,
    redact_auth_config,
    redact_dict,
    redact_headers,
    redact_payload,
    redact_text,
    redact_url,
)
from schema_lens.security.secrets import resolve_auth_config, resolve_secret, resolve_secret_field

__all__ = [
    "SecurityProfile",
    "AuthMaterial",
    "AuthResolutionError",
    "SecurityConfigError",
    "SecretResolutionError",
    "AuthProviderError",
    "SecurityConfig",
    "AuditConfig",
    "resolve_profile",
    "resolve_auth_material",
    "resolve_secret",
    "resolve_auth_config",
    "resolve_secret_field",
    "parse_security_config",
    "parse_audit_config",
    "REDACTED",
    "redact_dict",
    "redact_payload",
    "redact_headers",
    "redact_url",
    "redact_text",
    "redact_auth_config",
    "build_audit_record",
]
