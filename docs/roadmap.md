# SolrGuard Roadmap

This roadmap consolidates near-term and forward-looking workstreams in one place.

## Available now

- Solr compatibility and capability detection with fallback reporting
- Policy-as-code gates with approvals and exceptions metadata
- Security mode and privacy-safe/export-safe artifact controls
- Segment-aware analysis and governance summaries
- Rollout orchestration artifacts (canary, alias swap dry-run, rollback plan)
- API service mode with file-backed jobs and artifact retrieval
- Docker and Helm deployment assets

## Next (active planning)

- Major-version module migration plan (`schema_lens` -> `solrguard` imports)
- CLI/metric/Helm compatibility deprecation execution
- API auth/RBAC middleware hardening and audit extensions
- Additional first-party built-in plugins
- Enhanced report layout hooks and dashboard surfacing

## Future direction

- OIDC/SSO and enterprise identity integration
- Distributed worker execution and queue-backed job stores
- Live drift monitoring and streaming run updates
- Vector/hybrid and LTR governance expansions
- Richer enterprise dashboard and approvals UX
- Supply-chain hardening and signed release automation

## Detailed backlog documents

- API server backlog: [roadmap_api_server.md](roadmap_api_server.md)
- Enterprise next issues: [enterprise/backlog_next_issues.md](enterprise/backlog_next_issues.md)
- Deprecation schedule: [deprecation-schedule.md](deprecation-schedule.md)
- Module migration: [major-version-module-migration.md](major-version-module-migration.md)
