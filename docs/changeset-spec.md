# Changeset Spec v0.1.2

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
    type: "file" # "file" | "solr"
    path: "examples/docs.jsonl" # required for type=file
    format: "jsonl"
    id_field: "id"
    # solr source options (type=solr):
    # solr_url: "http://localhost:8983/solr"
    # collection: "products"
    # mode: "export" # "export" | "cursormark"
    # query: "*:*"
    # sort: "id asc"
    # fl: "id,title,text,category"
    # sample_n: 50000
    # batch_size: 500
    # out_sample_path: "out/docs_sample.jsonl"
  sample_n: 50000

queries:
  source:
    type: "file" # "file" | "log"
    path: "examples/queries.txt"
    format: "simple" # file: "simple" | "jsonl", log: "solr_params" | "jsonl"
  max_queries: 2000
  sampling:
    mode: "reservoir" # "top" | "reservoir"
    seed: 42
  sanitize:
    enabled: true
    rules:
      - type: "mask_email"
      - type: "mask_uuid"
      - type: "drop_param"
        name: "token"
      - type: "drop_param"
        name: "auth"

preflight:
  fail_on_risk: false

replay:
  capture:
    facets:
      enabled: true
      fields: ["category", "brand"]
      limit: 20
    track_numfound: true
    track_sort: true

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
    structured: false
    max_queries: 25
    max_docs_per_query: 3
```

## Required fields

- `baseline.solr_url`
- `baseline.collection`
- `data.docs_source.path` when `data.docs_source.type=file`
- `data.docs_source.solr_url` and `data.docs_source.collection` when `data.docs_source.type=solr`
- `queries.source.path`

## Supported operations

- `schema.field.update`
- `schema.fieldType.replace`
- `schema.analyzer.remove_filter`
- `queryparams.set`

## Notes

- `queryparams.set` affects replay parameters only.
- `queries.source.type=log` enables log extraction + canonical JSONL replay generation.
- `data.docs_source.type=solr` samples docs from Solr and writes reproducible JSONL output.
- Preflight always emits `schema_risk.json`; set `preflight.fail_on_risk=true` to block execution on HIGH risks.
- `replay.capture.facets.enabled=true` captures classic Solr facet counts during replay.
- `replay.capture.track_numfound` and `replay.capture.track_sort` enable extra diagnostics in compare/report output.
- `schema.analyzer.remove_filter.filter_class` can be a Java class (for example `solr.LowerCaseFilterFactory`) or the short filter name (`lowercase`).
- `shadow.allow_shared_configset_fallback=true` allows a non-isolated fallback when Solr blocks configset clone operations (401 on trusted base configsets). This is explicit and can affect baseline behavior.
- Empty `changes` is allowed with a warning.
