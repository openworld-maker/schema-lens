# Solr Compatibility Contract

SolrGuard provides a deterministic compatibility contract for Apache Solr targets.

## What is detected

- Solr version from `/admin/info/system` payloads
- capability flags derived from version contract
- missing capabilities and explicit fallback behavior

## Capability flags

- `collections_api`
- `schema_api`
- `config_api`
- `managed_resources`
- `vector_search`
- `ltr`
- `aliases`
- `metrics_api`
- `security_api`
- `package_manager`
- `streaming_expressions`
- `v2_api`

Backward-compatible flags used by runtime adapters remain available:

- `vector_query_supported`
- `structured_explain_supported`
- `metrics_json_supported`
- `configset_upload_supported`
- `package_manager_available`

## CLI

```bash
solrguard detect-capabilities --solr-url http://localhost:8983/solr
solrguard detect-capabilities --from-file examples/compat/solr9_system_info.json --out out/caps.json
solrguard compatibility --target http://localhost:8983/solr
solrguard compatibility --from-file examples/compat/solr10_system_info.json
```

## Runtime report fields

`report.json` / `compare.json` include compatibility metadata:

- detected version
- support tier
- confidence level
- missing capabilities
- fallback list

## Support framing

- Solr 8: supported with fallbacks
- Solr 9: recommended
- Solr 10: forward-ready framing
- Unknown/custom distro: low-confidence, safe degradations
