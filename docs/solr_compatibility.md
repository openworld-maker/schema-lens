# Solr Version Compatibility

SolrGuard uses a deterministic compatibility layer to detect Solr runtime support, expose capability flags, and downgrade behavior safely instead of crashing runs.

## Compatibility Philosophy

- Detect first, execute second.
- Prefer graceful fallbacks over hard failures.
- Record all compatibility decisions in artifacts (`compat.json`, `snapshot.json`, `run_manifest.json`, `report.json`).
- Keep probe behavior best-effort and low-risk.

## Version Support Matrix

| Solr family | Support tier | Confidence | Default posture |
| --- | --- | --- | --- |
| 8.x | `supported_with_fallbacks` | high | vector/structured explain may be disabled |
| 9.x | `recommended` | high | full governance tracks available |
| 10.x | `forward_ready` | medium | probes confirm behavior; assumptions are conservative |
| unknown/custom | `unknown` | low | safe defaults + explicit warnings |

## Capability Matrix by Feature

| Capability | Meaning | Typical fallback |
| --- | --- | --- |
| `metrics_json_supported` | `/admin/metrics` JSON available | use `/admin/mbeans` |
| `metrics_mbeans_supported` | `/admin/mbeans` available | disable perf capture if absent |
| `structured_explain_supported` | structured explain debug format available | raw explain parsing |
| `vector_supported` | vector fields/query support available | disable vector scenarios |
| `vector_native_hybrid_supported` | native hybrid vector execution | client-side hybrid simulation |
| `json_request_supported` | `/query` JSON request path available | `/select` fallback |
| `configset_upload_supported` | configset upload workflow available | local configset mode |
| `configset_download_supported` | configset download workflow available | local baseline configset path |
| `collections_api_supported` | collections APIs available | reduced rollout operations |
| `alias_ops_supported` | alias listing/swap operations available | skip alias dry-run |
| `luke_supported` | Luke/index inspection endpoint available | skip Luke stats |
| `ltr_possible` | LTR evaluation likely available | disable LTR impact checks |
| `feature_logging_possible` | LTR feature logging likely available | summary-only LTR notes |
| `package_manager_possible` | Solr package manager likely available | manual package/plugin deployment |

## Fallback Behavior

When capability gaps are found, SolrGuard emits explicit fallbacks and warnings in `compatibility.fallbacks` and `compatibility.warnings`.

Examples:

- "Using /admin/mbeans fallback because /admin/metrics JSON was not supported."
- "Structured explain unavailable; using raw explain output."
- "Vector support unavailable; vector scenarios skipped."

## SolrCloud vs Standalone Notes

- Deployment mode is detected from system payload fields and normalized to `solrcloud` or `standalone`.
- In `solrcloud` mode, collection/alias features are expected and probe-confirmed.
- In `standalone` mode, rollout paths that require collections/aliases are marked degraded when unavailable.

## Vector, LTR, and Metrics Notes

- Vector/hybrid simulation is gated by `vector_supported` and `vector_native_hybrid_supported`.
- LTR analysis is gated by `ltr_possible` and `feature_logging_possible`.
- Performance capture uses adapter selection: metrics JSON first, then mbeans fallback.

## Troubleshooting

1. Confirm system payload access (`/admin/info/system`) and auth settings.
2. Run `solrguard detect-capabilities --target <solr-url>` for a direct summary.
3. Inspect `compat.json` and `report.json` for `missing_capabilities`, `disabled_features`, and `fallbacks`.
4. For compare-env runs, inspect `environment_compare.compatibility.capability_mismatches`.

## Follow-up Tasks

1. richer Solr feature probing
2. package-manager/module detection
3. capability negotiation with plugins
4. per-feature minimum-version enforcement
5. compatibility telemetry (opt-in)
6. compatibility validation CLI command
7. mixed-cluster compatibility warning improvements
8. collection-level feature overrides
9. runtime probe caching
10. operator-facing compatibility dashboard widgets
