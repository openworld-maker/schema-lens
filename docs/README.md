# SolrGuard Documentation

Technical documentation for SolrGuard, the search change governance toolkit for Apache Solr.

## Choose your path

- I want to evaluate a Solr change quickly: [usage-guide.md](usage-guide.md)
- I want enterprise secure mode: [enterprise/security.md](enterprise/security.md)
- I want compatibility and fallback expectations: [compatibility.md](compatibility.md)
- I want detailed Solr version capability guidance: [solr_compatibility.md](solr_compatibility.md)
- I want policy and approvals guidance: [enterprise/policies.md](enterprise/policies.md)
- I want rollout orchestration (GitOps/canary/rollback): [enterprise/gitops.md](enterprise/gitops.md)
- I want deployment options (Docker/Helm/API): [deployment.md](deployment.md)
- I want to see sample report outputs quickly: [example-outputs.md](example-outputs.md)
- I want categorized runnable examples: [examples.md](examples.md)
- I am migrating from Schema-Lens: [migration-from-schema-lens.md](migration-from-schema-lens.md)

## Documentation map

### Getting started

- [usage-guide.md](usage-guide.md)
- [changeset-spec.md](changeset-spec.md)
- [architecture.md](architecture.md)

### Compatibility and safety

- [compatibility.md](compatibility.md)
- [solr_compatibility.md](solr_compatibility.md)
- [enterprise/compatibility-matrix.md](enterprise/compatibility-matrix.md)
- [roadmap_compatibility.md](roadmap_compatibility.md)
- [enterprise/security.md](enterprise/security.md)
- [security.md](security.md)
- [enterprise/privacy.md](enterprise/privacy.md)

### Governance and rollout

- [enterprise/policies.md](enterprise/policies.md)
- [enterprise/approvals-and-exceptions.md](enterprise/approvals-and-exceptions.md)
- [enterprise/gitops.md](enterprise/gitops.md)
- [enterprise/segmentation.md](enterprise/segmentation.md)
- [enterprise/evaluation-workflow.md](enterprise/evaluation-workflow.md)

### Platform integrations

- [api_server.md](api_server.md)
- [plugin_sdk.md](plugin_sdk.md)
- [example-outputs.md](example-outputs.md)
- [examples.md](examples.md)
- [enterprise/observability.md](enterprise/observability.md)
- [deployment.md](deployment.md)
- [enterprise/deployment.md](enterprise/deployment.md)

### Project direction and migration

- [roadmap.md](roadmap.md)
- [brand-positioning.md](brand-positioning.md)
- [migration-from-schema-lens.md](migration-from-schema-lens.md)
- [deprecation-schedule.md](deprecation-schedule.md)
- [major-version-module-migration.md](major-version-module-migration.md)
- [release-notes-solrguard.md](release-notes-solrguard.md)
- [roadmap_api_server.md](roadmap_api_server.md)
- [roadmap_security.md](roadmap_security.md)
- [enterprise/backlog_next_issues.md](enterprise/backlog_next_issues.md)

## Trust and operations notes

- Compatibility contract and fallback behavior are documented and tested.
- Security and privacy controls default to safer export modes when configured.
- Governance records (policy, approvals, exceptions, audit metadata) are artifact-driven.
- API mode is local-first and file-backed for deterministic run/state inspection.
