# Observability Integrations

SolrGuard emits run lifecycle telemetry for governance workflows.

## Outputs

- `observability_events.jsonl`
- `prometheus_metrics.prom`
- `otel_spans.json`
- `webhook_deliveries.json`

## Phase timing coverage

- startup/config parse
- auth/security init
- snapshot + compatibility detection
- replay/compare
- policy/gate
- report generation
- artifact export
- notifications

## Examples

- `examples/observability/prometheus_config.md`
- `examples/observability/grafana_dashboard.json`
- `examples/observability/webhook_payload.json`
