# Changeset Spec v0.1

```yaml
schema_lens_version: 1

baseline:
  solr_url: "http://localhost:8983/solr"
  collection: "products"
  request_defaults:
    rows: 10
    fl: "id,score"
    defType: "edismax"
    extra_params:
      fq: []
      qf: "title^3 text"
      pf: "title^10"

shadow:
  mode: "solrcloud"
  solr_url: "http://localhost:8983/solr"
  collection_name_template: "{collection}__shadow__{ts}"
  num_shards: 1
  replication_factor: 1
  cleanup: true
  allow_shared_configset_fallback: false

data:
  docs_source:
    type: "file"
    path: "examples/docs.jsonl"
    format: "jsonl"
    id_field: "id"
  sample_n: 50000

queries:
  source:
    type: "file"
    path: "examples/queries.txt"
    format: "simple"
  max_queries: 2000

changes:
  - op: "schema.field.update"
    field: "title"
    set:
      type: "text_en"
  - op: "schema.fieldType.replace"
    name: "text_general"
    with: "text_en"
  - op: "schema.analyzer.remove_filter"
    fieldType: "text_general"
    analyzer: "index"
    filter_class: "solr.LowerCaseFilterFactory"
  - op: "queryparams.set"
    set:
      qf: "title^5 text"
      pf: "title^20"

evaluation:
  k: 10
  metrics:
    - overlap
    - jaccard
    - kendall_tau
  explain:
    enabled: true
    max_queries: 25
    max_docs_per_query: 3
```

## Required fields

- `baseline.solr_url`
- `baseline.collection`
- `data.docs_source.path`
- `queries.source.path`

## Supported operations

- `schema.field.update`
- `schema.fieldType.replace`
- `schema.analyzer.remove_filter`
- `queryparams.set`

## Notes

- `queryparams.set` affects replay parameters only.
- `schema.analyzer.remove_filter.filter_class` can be a Java class (for example `solr.LowerCaseFilterFactory`) or the short filter name (`lowercase`).
- `shadow.allow_shared_configset_fallback=true` allows a non-isolated fallback when Solr blocks configset clone operations (401 on trusted base configsets). This is explicit and can affect baseline behavior.
- Empty `changes` is allowed with a warning.
