# Security Policy

## Reporting a vulnerability

Please report security issues privately to project maintainers rather than opening a public issue with exploit details.

Include:

- affected version/commit
- reproduction steps
- impact scope
- suggested remediation (if available)

## Security model highlights

- local-first execution by default
- redaction support for credentials and sensitive fields
- no-sensitive-artifact mode for governance-safe exports
- privacy controls for query/doc masking and retention metadata

## Scope notes

SolrGuard helps evaluate and govern change safety, but it does not replace network, identity, or cluster hardening controls in production environments.
