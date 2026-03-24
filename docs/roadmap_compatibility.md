# Compatibility Roadmap

Issue-sized next steps for SolrGuard compatibility detection.

1. Add dedicated `solrguard compat inspect` command with live probe breakdown and confidence scoring.
2. Implement probe caching keyed by `solr_url + collection + auth fingerprint` to reduce repeated admin calls.
3. Detect Solr package-manager and optional module state from runtime APIs.
4. Add mixed-cluster warning rules for SolrCloud nodes returning heterogeneous capability results.
5. Support collection-level overrides for vector/LTR capability flags.
6. Add plugin capability negotiation contract so plugins can declare hard/soft capability requirements.
7. Expand fixture corpus with distro variants (managed service distributions, security-restricted endpoints).
8. Add API endpoint summaries for environment capability mismatch risk scoring.
9. Add compatibility telemetry export (opt-in) for fleet-level governance dashboards.
10. Add operator-focused dashboard widgets that highlight degraded modes and fallback frequency.
