"""Aggregate performance and cost impact from replay and Solr snapshots."""

from __future__ import annotations

from typing import Any

from schema_lens.perf.grouping import classify_query
from schema_lens.perf.index_stats import compute_index_delta, detect_schema_storage_impacts
from schema_lens.perf.percentiles import summarize_percentiles


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cache_deltas(
    baseline_caches: dict[str, dict[str, float]],
    shadow_caches: dict[str, dict[str, float]],
) -> dict[str, Any]:
    names = sorted(set(baseline_caches.keys()) | set(shadow_caches.keys()))
    out: dict[str, Any] = {}
    for name in names:
        base = baseline_caches.get(name, {})
        shadow = shadow_caches.get(name, {})
        row: dict[str, Any] = {}
        for key in ("hits", "inserts", "evictions", "hitratio"):
            base_value = _safe_float(base.get(key)) or 0.0
            shadow_value = _safe_float(shadow.get(key)) or 0.0
            row[key] = {
                "baseline": base_value,
                "shadow": shadow_value,
                "delta": shadow_value - base_value,
                "delta_pct": ((shadow_value - base_value) / base_value * 100.0)
                if base_value
                else None,
            }
        churn_den = row["inserts"]["shadow"] or 0.0
        row["churn_ratio"] = (
            row["evictions"]["shadow"] / churn_den if churn_den else None
        )
        out[name] = row
    return out


def _summarize_samples(samples: list[float], percentiles: list[int]) -> dict[str, Any]:
    if not samples:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "avg": 0.0,
            **summarize_percentiles([], percentiles),
        }
    return {
        "count": len(samples),
        "min": min(samples),
        "max": max(samples),
        "avg": sum(samples) / len(samples),
        **summarize_percentiles(samples, percentiles),
    }


def analyze_performance(
    *,
    replay_data: dict[str, Any],
    compare_data: dict[str, Any],
    baseline_snapshot: dict[str, Any],
    shadow_snapshot: dict[str, Any],
    changes: list[dict[str, Any]],
    percentiles: list[int],
) -> dict[str, Any]:
    pairs = replay_data.get("pairs", [])
    query_samples: list[dict[str, Any]] = []
    group_buckets: dict[str, dict[str, list[float]]] = {}

    for pair in pairs:
        query = pair.get("query", {})
        params = query.get("params", {}) if isinstance(query.get("params"), dict) else {}
        facet_counts = pair.get("baseline", {}).get("facet_counts") or pair.get(
            "shadow", {}
        ).get("facet_counts")
        labels = classify_query(
            params=params,
            request_mode=query.get("request_mode"),
            scenario_mode=None,
            facet_counts=facet_counts if isinstance(facet_counts, dict) else None,
        )
        base_meta = pair.get("baseline", {}).get("raw_response_meta", {})
        shadow_meta = pair.get("shadow", {}).get("raw_response_meta", {})
        row = {
            "query_id": query.get("id"),
            "labels": labels,
            "baseline_client_latency_ms": _safe_float(base_meta.get("client_latency_ms")),
            "shadow_client_latency_ms": _safe_float(shadow_meta.get("client_latency_ms")),
            "baseline_qtime_ms": _safe_float(base_meta.get("QTime")),
            "shadow_qtime_ms": _safe_float(shadow_meta.get("QTime")),
            "baseline_numFound": base_meta.get("numFound"),
            "shadow_numFound": shadow_meta.get("numFound"),
        }
        query_samples.append(row)

        for label in labels:
            bucket = group_buckets.setdefault(
                label,
                {
                    "baseline_client_latency_ms": [],
                    "shadow_client_latency_ms": [],
                    "baseline_qtime_ms": [],
                    "shadow_qtime_ms": [],
                },
            )
            for key in tuple(bucket.keys()):
                value = row.get(key)
                if isinstance(value, (int, float)):
                    bucket[key].append(float(value))

    overall = {
        "baseline_client_latency_ms": _summarize_samples(
            [
                row["baseline_client_latency_ms"]
                for row in query_samples
                if isinstance(row.get("baseline_client_latency_ms"), (int, float))
            ],
            percentiles,
        ),
        "shadow_client_latency_ms": _summarize_samples(
            [
                row["shadow_client_latency_ms"]
                for row in query_samples
                if isinstance(row.get("shadow_client_latency_ms"), (int, float))
            ],
            percentiles,
        ),
        "baseline_qtime_ms": _summarize_samples(
            [
                row["baseline_qtime_ms"]
                for row in query_samples
                if isinstance(row.get("baseline_qtime_ms"), (int, float))
            ],
            percentiles,
        ),
        "shadow_qtime_ms": _summarize_samples(
            [
                row["shadow_qtime_ms"]
                for row in query_samples
                if isinstance(row.get("shadow_qtime_ms"), (int, float))
            ],
            percentiles,
        ),
    }

    grouped: dict[str, Any] = {}
    for label, bucket in group_buckets.items():
        grouped[label] = {
            metric: _summarize_samples(values, percentiles) for metric, values in bucket.items()
        }

    perf = {
        "enabled": True,
        "overall": overall,
        "grouped": grouped,
        "per_query": query_samples,
        "caches": _cache_deltas(
            baseline_snapshot.get("caches", {}),
            shadow_snapshot.get("caches", {}),
        ),
        "index": {
            "baseline": baseline_snapshot.get("index", {}),
            "shadow": shadow_snapshot.get("index", {}),
            "delta": compute_index_delta(
                baseline_snapshot.get("index", {}),
                shadow_snapshot.get("index", {}),
            ),
            "schema_heuristics": detect_schema_storage_impacts(changes),
        },
        "callouts": [],
    }

    shadow_p95 = perf["overall"]["shadow_client_latency_ms"].get("p95", 0.0)
    base_p95 = perf["overall"]["baseline_client_latency_ms"].get("p95", 0.0)
    if base_p95 and shadow_p95:
        delta_pct = (shadow_p95 - base_p95) / base_p95 * 100.0
        if abs(delta_pct) >= 10.0:
            perf["callouts"].append(
                f"Shadow p95 client latency changed {delta_pct:+.1f}% versus baseline."
            )

    filter_cache = perf["caches"].get("filterCache", {})
    evictions = filter_cache.get("evictions", {})
    if isinstance(evictions, dict) and isinstance(evictions.get("delta_pct"), (int, float)):
        if abs(float(evictions["delta_pct"])) >= 25.0:
            perf["callouts"].append(
                f"filterCache evictions changed {float(evictions['delta_pct']):+.1f}%."
            )

    compare_data["performance"] = perf
    return perf
