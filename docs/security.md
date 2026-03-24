# Enterprise Security & Privacy

SolrGuard security mode enables safe execution against enterprise Solr environments while preventing secret leakage into manifests, reports, API request logs, and plugin artifacts.

## Design goals

- support real enterprise auth patterns (basic, bearer, mTLS, plugin providers)
- resolve secrets from environment and files safely
- redact secrets deterministically across logs/artifacts
- provide privacy profiles with clear artifact persistence behavior
- capture audit metadata for governance and compliance workflows

## Supported auth modes

- `none`: local/dev mode
- `basic`: username/password
- `bearer`: token-based auth
- `mtls`: client cert/key + optional CA file
- `plugin`: auth provider plugins through the plugin SDK

## Secret resolution rules

Supported input forms:

- plain string values
- env reference: `${ENV_VAR}`
- file reference: `file:/path/to/secret.txt`
- object form: `{from_env: VAR}`, `{from_file: /path}`, `{value: ...}`

Resolution behavior:

- missing/empty required secrets fail validation with non-secret error messages
- resolved secrets are never persisted back to run artifacts
- redacted config is persisted using `***REDACTED***`

## Redaction behavior

Redaction applies to:

- auth config payloads
- run manifests and report payload snippets
- API request payload persistence
- headers and authorization values
- URLs that include embedded credentials
- text logs with common secret patterns

Default sensitive keys include:

- `password`, `passwd`, `token`, `authorization`, `api_key`, `secret`, `private_key`, `key_file`, `cert_file`

## Security profiles

- `local-dev`: full artifacts, secret redaction still enforced.
- `enterprise-safe`: redacted artifacts; raw request/doc/debug persistence disabled by default.
- `no-sensitive-artifacts`: suppresses sensitive artifact persistence.
- `summary-only`: keeps only summary/report/audit-style artifacts.

## Audit trail

Captured fields include:

- run id, timestamp, requested_by, team, ticket_id
- environment label, target URLs/collections
- auth modes used
- security profile
- plugin list
- run outcome marker

Audit output is persisted without secrets.

## API mode interactions

- API request payload persistence uses security redaction helpers.
- API audit middleware logs principal/roles/outcome metadata.
- artifact serving remains constrained to tracked job artifacts.

## Plugin interactions

- plugin config is persisted in redacted form.
- plugin outputs can mark payload as `{"sensitive": true}`.
- sensitive plugin payloads are suppressed in `no-sensitive-artifacts` and `summary-only` profiles.

## Operational recommendations

- prefer env/file secret references for production and CI/CD.
- avoid inline secrets outside local dev.
- use `enterprise-safe` as default for shared environments.
- use `summary-only` for broad report sharing.

## Follow-up Tasks

1. Vault / secret manager integration
2. Kerberos / SPNEGO provider
3. request signing auth provider
4. fine-grained field masking policies
5. per-artifact encryption at rest
6. RBAC for API server
7. per-tenant privacy policies
8. admin-configurable audit sinks
9. secret rotation support
10. compliance mode (SOC2/GDPR-friendly artifact controls)
