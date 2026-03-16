# Policy-as-Code

SolrGuard policy workflows are deterministic and auditable.

## Components

- reusable policy bundles
- gate evaluation
- promotion-aware policy intent
- report rendering of pass/fail/warn evidence

## CLI

```bash
solrguard gate --compare out/run/compare.json --policy examples/policy/gate_default.yaml
solrguard ci summarize --compare out/run/compare.json --policy examples/policy/gate_default.yaml --out out/summary.md
```

## Bundle examples

- `examples/governance/prod_promotion_policy.yaml`
- `examples/policy/perf_gate_default.yaml`
- `examples/policy/tenant_specific_policy.yaml`
