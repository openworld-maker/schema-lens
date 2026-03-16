# Enterprise Security Mode

SolrGuard supports enterprise-safe execution with credential abstraction and redaction-first artifact handling.

## Supported auth modes

- Basic
- Bearer/JWT
- mTLS
- Plugin-based auth providers

## Safe defaults

- secret redaction in logs/reports/manifests
- optional `no_sensitive_artifacts` behavior via security profile
- audit metadata persisted in `audit.json`

## Examples

- `examples/security/basic_auth_env.yaml`
- `examples/security/bearer_token_env.yaml`
- `examples/security/mtls_config.yaml`

## API mode

API service supports pluggable auth provider + RBAC policy and request audit trails (`logs/api_audit.jsonl`).
