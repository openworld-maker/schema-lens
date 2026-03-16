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

After `solrguard run`, scrape metrics from:

- `out/<run>/prometheus_metrics.prom`

Exported metric names:

- `solrguard_runs_total`
- `solrguard_runs_failed_total`
- `solrguard_high_risk_queries_total`
- `solrguard_gate_failures_total`
- `solrguard_p95_latency_regression_pct`
- `solrguard_cache_eviction_regression_pct`
