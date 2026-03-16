# Migration from Schema-Lens to SolrGuard

SolrGuard is the new product identity for Schema-Lens.

## What changed

- Product name: `Schema-Lens` -> `SolrGuard`
- Primary CLI command: `schema-lens` -> `solrguard`
- API service identity string: `schema-lens-api` -> `solrguard-api`
- CI/report headings updated to SolrGuard branding

## Old vs new commands

| Old | New |
|---|---|
| `schema-lens run ...` | `solrguard run ...` |
| `schema-lens gate ...` | `solrguard gate ...` |
| `schema-lens api serve ...` | `solrguard api serve ...` |
| `schema-lens compatibility ...` | `solrguard compatibility ...` |

## Backward compatibility guarantees (current release)

- `schema-lens` CLI alias remains supported.
- Python import path remains `schema_lens`.
- Changeset key `schema_lens_version` remains supported (preferred key: `solrguard_version`).
- Legacy API auth header `x-schema-lens-token` remains accepted.
- Legacy Helm chart path `helm/schema-lens` remains available.
- Legacy Prometheus aliases `schema_lens_*` remain emitted.

## Known changes

- Docs/examples now use `solrguard` by default.
- Docker and Helm metadata use SolrGuard branding.

## Deprecation path

- `schema-lens` command alias is planned for deprecation in a future major release.
- `schema_lens` import path remains stable until a dedicated major migration plan is published.
- See explicit timelines in `docs/deprecation-schedule.md`.

## Recommended migration timeline

1. Immediate: switch automation to `solrguard` command.
2. Near-term: update internal docs and runbooks to SolrGuard naming.
3. Later: monitor release notes for alias deprecation milestones.
