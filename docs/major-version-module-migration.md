# Major Version Plan: Python Module Rename

Goal: migrate public imports from `schema_lens` to `solrguard` with minimal disruption.

## Current state (v0.x)

- Canonical implementation package: `schema_lens`
- New shim package: `solrguard` (re-exports version and CLI app)
- CLI commands: `solrguard` (primary), `schema-lens` (legacy alias)

## Planned migration (v1.x)

1. Introduce full `solrguard.*` import surface (phase-in).
2. Keep `schema_lens.*` as import shims with deprecation warnings.
3. Add codemod/migration script for import rewrites.
4. Remove `schema_lens.*` shims in next major release window.

## Compatibility commitments

- No import breakage within v0.x.
- Deprecation warnings should be emitted before removal windows.
- CLI and docs continue to provide migration examples.

## Risks and mitigations

- Risk: ecosystem break from import-path cutover.
- Mitigation: staged shims, explicit timeline, dual-path tests in CI.
