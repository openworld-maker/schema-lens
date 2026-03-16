# Deprecation Schedule

This schedule defines compatibility windows for SolrGuard rename transitions.

## 1) CLI alias: `schema-lens`

- Current: supported with runtime deprecation warning.
- Planned support window: through `v0.5.x`.
- Planned removal: next major after `v1.0` readiness announcement.
- Preferred command: `solrguard`.

## 2) Helm chart path: `helm/schema-lens`

- Current: retained as legacy path.
- Primary chart path: `helm/solrguard`.
- Planned support window for legacy path: through `v0.6.x`.
- Planned removal: first major release after migration notice cycle.

## 3) Prometheus metric aliases: `schema_lens_*`

- Current: dual emit (`solrguard_*` primary + `schema_lens_*` aliases).
- Planned support window for aliases: through `v0.6.x`.
- Planned removal: major release after exporter migration guide is published.

## 4) Changeset version key: `schema_lens_version`

- Current: supported with validator deprecation warning.
- Preferred key: `solrguard_version`.
- Planned support window for legacy key: through `v0.6.x`.
- Planned removal: major release with schema migration tooling.

## 5) Python imports: `schema_lens.*`

- Current: canonical implementation path.
- Transition path: `solrguard` shim package added now; full import migration follows major-version plan.
- See `docs/major-version-module-migration.md`.
