# Security Roadmap TODOs

## Auth and secret management

- [ ] Integrate Vault/secret manager providers
- [ ] Add Kerberos/SPNEGO auth provider
- [ ] Add request-signing auth provider
- [ ] Add secret rotation primitives and grace windows

## Redaction and privacy

- [ ] Add policy-driven field masking by artifact type
- [ ] Add per-tenant privacy policy mapping
- [ ] Add stricter summary-only export templates
- [ ] Add compliance presets (SOC2/GDPR/PII-sensitive)

## Artifact and audit hardening

- [ ] Add per-artifact encryption-at-rest support
- [ ] Add configurable external audit sinks
- [ ] Add tamper-evident audit chain output

## API security integration

- [ ] Add API RBAC policy packs and role templates
- [ ] Add authN/authZ docs for gateway/OIDC deployments
- [ ] Add sensitive-artifact denial reasons in artifact manifest responses
