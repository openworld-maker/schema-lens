# GitOps and Rollout Orchestration

SolrGuard includes rollout planning commands with simulation-first defaults.

## Commands

```bash
solrguard rollout git-drift --solr-url URL --collection NAME --local-configset-dir DIR --out drift.json
solrguard rollout canary-plan --baseline-collection BASE --canary-collection CANARY --out canary_plan.json
solrguard rollout alias-swap-plan --alias products --from-collection products_v1 --to-collection products_v2 --out alias_plan.json
solrguard rollout rollback-plan --alias products --previous-collection products_v1 --out rollback_plan.json
solrguard rollout verify-post-cutover --canary-compare out/canary/compare.json --prod-compare out/prod/compare.json --out verify.json
```

## Examples

- `examples/rollout/git_configset_compare.yaml`
- `examples/rollout/canary_plan.yaml`
- `examples/rollout/alias_swap_plan.json`
