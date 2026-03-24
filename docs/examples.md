# SolrGuard Example Catalog

Use this page to find runnable examples quickly.

## Quick evaluation

- `examples/changesets/fieldtype-change.yaml`
- `examples/changesets/no-changes.yaml`
- `examples/changesets/queryparams-only.yaml`
- `examples/changesets/procurement-synonym-rewrite.yaml`
- `solrguard check --live --out out/check_live`
- `solrguard check examples/changesets/fieldtype-change.yaml --out out/check_demo`

## 3-minute offline demo (no Solr required)

- `examples/demo/README.md`
- `examples/demo/replay_minimal.json`
- `examples/demo/run_manifest_minimal.json`
- `examples/demo/expected/compare.json`
- `examples/demo/expected/report.json`

## Policy workflows

- `examples/policy/gate_default.yaml`
- `examples/policy/perf_gate_default.yaml`
- `examples/governance/prod_promotion_policy.yaml`
- `examples/governance/approval_metadata.json`
- `examples/governance/exception_record.json`

## Rollout planning

- `examples/rollout/git_configset_compare.yaml`
- `examples/rollout/canary_plan.yaml`
- `examples/rollout/alias_swap_plan.json`
- `examples/enterprise/gitops/canary_rollout_plan.yaml`

## Enterprise security mode

- `examples/security/basic_auth_env.yaml`
- `examples/security/bearer_token_env.yaml`
- `examples/security/mtls_auth.yaml`
- `examples/security/enterprise_safe_profile.yaml`
- `examples/security/summary_only_profile.yaml`
- `examples/enterprise/security/solr9_secured_changeset.yaml`

## Privacy-safe exports

- `examples/privacy/export_safe_mode.yaml`
- `examples/privacy/pii_masking_profile.yaml`
- `examples/enterprise/privacy/export_safe_changeset.yaml`

## Observability integrations

- `examples/observability/grafana_dashboard.json`
- `examples/observability/prometheus_config.md`
- `examples/observability/webhook_payload.json`
- `examples/enterprise/observability/prom_webhook_changeset.yaml`

## API/service mode

- `examples/api/create_run_from_path.json`
- `examples/api/create_run_inline.json`
- `examples/api/compare_env_request.json`
- `examples/api/gate_request.json`

## CI / PR safety signals

- `solrguard check examples/changesets/fieldtype-change.yaml --fail-on-risk HIGH_RISK`
- `solrguard check --compare-input out/demo/compare.json --pr-comment-out out/pr_comment.md`
- `solrguard queries ingest --from solr_request.log --out out/queries_ingested.jsonl`
