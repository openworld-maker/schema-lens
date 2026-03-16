# SolrGuard Examples Index

Examples are grouped by evaluation and governance workflow stage.

Fastest runnable path:

```bash
./scripts/first_time_evaluator.sh
```

Offline quickstart (no Solr required):

```bash
solrguard compare --replay examples/demo/replay_minimal.json --out out/demo_offline/compare.json
solrguard report --compare out/demo_offline/compare.json --manifest examples/demo/run_manifest_minimal.json --replay examples/demo/replay_minimal.json --out out/demo_offline
```

Categorized index: [docs/examples.md](../docs/examples.md)

## Quick evaluation

- `changesets/fieldtype-change.yaml`
- `changesets/no-changes.yaml`
- `changesets/queryparams-only.yaml`
- `changesets/procurement-synonym-rewrite.yaml`
- `changesets/vector-hybrid-demo.yaml`
- `changesets/perf_estimator_example.yaml`

## Compatibility and migration fixtures

- `compat/solr8_system_info.json`
- `compat/solr9_system_info.json`
- `compat/solr10_system_info.json`
- `changesets/legacy-schema-lens-version.yaml` (legacy compatibility fixture)

## Enterprise secure/governance usage

- `enterprise/security/solr9_secured_changeset.yaml`
- `enterprise/governance/prod_promotion_changeset.yaml`
- `governance/approval_metadata.json`
- `governance/exception_record.json`
- `governance/prod_promotion_policy.yaml`

## Rollout orchestration

- `rollout/git_configset_compare.yaml`
- `rollout/canary_plan.yaml`
- `rollout/alias_swap_plan.json`
- `enterprise/gitops/canary_rollout_plan.yaml`

## Observability and privacy

- `observability/grafana_dashboard.json`
- `observability/webhook_payload.json`
- `enterprise/observability/prom_webhook_changeset.yaml`
- `privacy/pii_masking_profile.yaml`
- `privacy/export_safe_mode.yaml`
- `enterprise/privacy/export_safe_changeset.yaml`

## API and deployment

- `api/create_run_from_path.json`
- `api/create_run_inline.json`
- `api/compare_env_request.json`
- `api/gate_request.json`
- `deploy/docker_run.md`
- `enterprise/deployment/helm_values_enterprise.yaml`
- `enterprise/ci/github_actions_promotion_gate.yml`
