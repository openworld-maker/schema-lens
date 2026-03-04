# Changeset Spec v0.1.3

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
  # when configset patch ops upload new configsets, promote to trusted clone for
  # SolrCloud environments that enforce trusted configsets:
  promote_uploaded_configset_trusted: true
  # optional local directory baseline when configset patch ops are used:
  # baseline_configset_dir: "examples/configsets/base_cfg"

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

  - op: "schema.synonym.update"
    mode: "replace" # replace | patch_append | patch_merge
    source_file: "examples/synonyms/procurement_synonyms_v2.txt"
    target:
      files:
        - path: "conf/synonyms.txt"

  - op: "schema.stopwords.update"
    mode: "patch_merge" # replace | patch_append | patch_merge
    source_file: "examples/stopwords/procurement_stopwords_v2.txt"
    target:
      files:
        - path: "conf/stopwords.txt"

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
  rewrite_diff:
    enabled: true
    max_queries: 25
    debug_mode: "debugQuery" # "debugQuery" | "results"
    clause_spike_threshold: 5
    always_for_high_risk: true
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
- `schema.synonym.update`
- `schema.stopwords.update`
- `queryparams.set`

## Configset update ops

- `schema.synonym.update` and `schema.stopwords.update` apply to shadow configset files.
- `target.files[*].path` points to configset-relative paths (for example `conf/synonyms.txt`).
- Paths can be `conf/<file>` or root style `<file>` depending on configset layout.
- `source_file` can be set at op-level or per target file entry.
- `mode` options:
  - `replace`: overwrite target with source content.
  - `patch_append`: append source lines after existing lines.
  - `patch_merge`: deterministic unique line merge of existing + source.
- When these ops are present, schema-lens builds an isolated patched configset and creates the
  shadow collection with `collection.configName=<patched_configset>`.
- By default, schema-lens then promotes uploaded configsets to a trusted clone for environments
  where untrusted uploaded configsets are restricted (`shadow.promote_uploaded_configset_trusted`).

## Notes

- `queryparams.set` affects replay/debug request parameters only.
- `queries.source.type=log` enables log extraction + canonical JSONL replay generation.
- `data.docs_source.type=solr` samples docs from Solr and writes reproducible JSONL output.
- Preflight always emits `schema_risk.json`; set `preflight.fail_on_risk=true` to block execution.
- `replay.capture.facets.enabled=true` captures classic Solr facet counts during replay.
- `evaluation.rewrite_diff.enabled=true` captures parser/rewrite debug payloads and computes
  query rewrite impact heuristics.
- `shadow.allow_shared_configset_fallback=true` allows non-isolated fallback only for plain
  configset clone path (no file patching).
- Empty `changes` is allowed with a warning.
