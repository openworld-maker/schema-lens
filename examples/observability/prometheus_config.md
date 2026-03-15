# Prometheus Integration

Enable observability in your changeset:

```yaml
observability:
  enabled: true
  prometheus:
    enabled: true
  otel:
    enabled: true
  webhooks:
    enabled: false
```

After `schema-lens run`, scrape metrics from:

- `out/<run>/prometheus_metrics.prom`

Exported metric names:

- `schema_lens_runs_total`
- `schema_lens_runs_failed_total`
- `schema_lens_high_risk_queries_total`
- `schema_lens_gate_failures_total`
- `schema_lens_p95_latency_regression_pct`
- `schema_lens_cache_eviction_regression_pct`
