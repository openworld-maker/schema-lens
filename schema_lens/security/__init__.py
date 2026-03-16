"""Security primitives for SolrGuard enterprise mode."""

from schema_lens.security.audit import build_audit_record
from schema_lens.security.auth import AuthMaterial, AuthResolutionError, resolve_auth_material
from schema_lens.security.profiles import SecurityProfile, resolve_profile
from schema_lens.security.redaction import redact_auth_config, redact_headers, redact_payload

__all__ = [
    "SecurityProfile",
    "AuthMaterial",
    "AuthResolutionError",
    "resolve_profile",
    "resolve_auth_material",
    "redact_payload",
    "redact_headers",
    "redact_auth_config",
    "build_audit_record",
]
