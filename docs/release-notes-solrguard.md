# Release Notes: SolrGuard Rename

Schema-Lens has evolved into **SolrGuard**.

## Why this rename

The project now serves a broader mission than simulation alone: enterprise-ready search change governance for Apache Solr.

## Highlights

- primary product and CLI branding moved to SolrGuard
- compatibility detection and governance workflows emphasized
- docs/examples/deployment assets updated to governance-first language

## Migration summary

- use `solrguard` instead of `schema-lens`
- `schema-lens` remains as a legacy alias in this release
- Python module path stays `schema_lens` for now

## Compatibility

- old command alias retained
- existing changeset format retained
- legacy API token header retained

## Next planned follow-ups

- formal timeline for legacy alias deprecation
- evaluate package import rename strategy for a future major release

See:

- `docs/deprecation-schedule.md`
- `docs/major-version-module-migration.md`
