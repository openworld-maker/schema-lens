"""Prometheus text-format metric helpers."""

from __future__ import annotations

from typing import Any


_PROM_HELP = {
    "solrguard_runs_total": "Total SolrGuard runs observed",
    "solrguard_runs_failed_total": "Total failed SolrGuard runs observed",
    "solrguard_high_risk_queries_total": "Total high-risk queries observed across runs",
    "solrguard_gate_failures_total": "Total gate failures observed",
    "solrguard_p95_latency_regression_pct": "Latest run p95 latency regression percent",
    "solrguard_cache_eviction_regression_pct": "Latest run cache eviction regression percent",
    "schema_lens_runs_total": "Legacy alias metric: total SolrGuard runs observed",
    "schema_lens_runs_failed_total": "Legacy alias metric: total failed SolrGuard runs observed",
    "schema_lens_high_risk_queries_total": "Legacy alias metric: high-risk queries observed across runs",
    "schema_lens_gate_failures_total": "Legacy alias metric: gate failures observed",
    "schema_lens_p95_latency_regression_pct": "Legacy alias metric: latest run p95 latency regression percent",
    "schema_lens_cache_eviction_regression_pct": "Legacy alias metric: latest run cache eviction regression percent",
}


class PrometheusMetrics:
    def __init__(self) -> None:
        self.values: dict[str, float] = {
            "solrguard_runs_total": 0.0,
            "solrguard_runs_failed_total": 0.0,
            "solrguard_high_risk_queries_total": 0.0,
            "solrguard_gate_failures_total": 0.0,
            "solrguard_p95_latency_regression_pct": 0.0,
            "solrguard_cache_eviction_regression_pct": 0.0,
            "schema_lens_runs_total": 0.0,
            "schema_lens_runs_failed_total": 0.0,
            "schema_lens_high_risk_queries_total": 0.0,
            "schema_lens_gate_failures_total": 0.0,
            "schema_lens_p95_latency_regression_pct": 0.0,
            "schema_lens_cache_eviction_regression_pct": 0.0,
        }

    def observe_run(
        self,
        *,
        failed: bool,
        high_risk_queries: int,
        gate_failed: bool,
        p95_latency_regression_pct: float,
        cache_eviction_regression_pct: float,
    ) -> None:
        self.values["solrguard_runs_total"] += 1
        self.values["schema_lens_runs_total"] += 1
        if failed:
            self.values["solrguard_runs_failed_total"] += 1
            self.values["schema_lens_runs_failed_total"] += 1
        self.values["solrguard_high_risk_queries_total"] += float(max(high_risk_queries, 0))
        self.values["schema_lens_high_risk_queries_total"] += float(max(high_risk_queries, 0))
        if gate_failed:
            self.values["solrguard_gate_failures_total"] += 1
            self.values["schema_lens_gate_failures_total"] += 1
        self.values["solrguard_p95_latency_regression_pct"] = float(p95_latency_regression_pct)
        self.values["schema_lens_p95_latency_regression_pct"] = float(p95_latency_regression_pct)
        self.values["solrguard_cache_eviction_regression_pct"] = float(cache_eviction_regression_pct)
        self.values["schema_lens_cache_eviction_regression_pct"] = float(cache_eviction_regression_pct)

    def render_text(self) -> str:
        lines: list[str] = []
        for name, value in self.values.items():
            lines.append(f"# HELP {name} {_PROM_HELP[name]}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines) + "\n"


def build_metrics_from_compare(compare_data: dict[str, Any], failed: bool = False) -> PrometheusMetrics:
    metrics = PrometheusMetrics()
    diffs = compare_data.get("diffs", []) if isinstance(compare_data, dict) else []
    high_risk = len([row for row in diffs if isinstance(row, dict) and row.get("risk_severity") == "HIGH"])

    perf = compare_data.get("performance", {}) if isinstance(compare_data, dict) else {}
    overall = perf.get("overall", {}) if isinstance(perf, dict) else {}
    cache_section = perf.get("caches", {}) if isinstance(perf, dict) else {}
    filter_cache = cache_section.get("filterCache", {}) if isinstance(cache_section, dict) else {}
    evictions = filter_cache.get("evictions", {}) if isinstance(filter_cache, dict) else {}

    base_p95 = 0.0
    shadow_p95 = 0.0
    base_lat = overall.get("baseline_client_latency_ms", {}) if isinstance(overall, dict) else {}
    sh_lat = overall.get("shadow_client_latency_ms", {}) if isinstance(overall, dict) else {}
    if isinstance(base_lat, dict):
        base_p95 = float(base_lat.get("p95", 0.0) or 0.0)
    if isinstance(sh_lat, dict):
        shadow_p95 = float(sh_lat.get("p95", 0.0) or 0.0)
    p95_delta = ((shadow_p95 - base_p95) / base_p95 * 100.0) if base_p95 else 0.0

    cache_delta = float(evictions.get("delta_pct", 0.0) or 0.0) if isinstance(evictions, dict) else 0.0

    metrics.observe_run(
        failed=failed,
        high_risk_queries=high_risk,
        gate_failed=False,
        p95_latency_regression_pct=p95_delta,
        cache_eviction_regression_pct=cache_delta,
    )
    return metrics
