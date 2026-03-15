# Changeset Spec v0.2.0

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

vector:
  enabled: true
  field: "emb"
  dimension: 8
  similarity: "cosine" # cosine | dot | euclidean
  query_vector_policy: "skip" # skip | fail
  embedding_source:
    type: "none" # file | none
    # path: "examples/vectors/embeddings_small.jsonl"
    # id_field: "id"
    # vector_field: "emb"
  scenarios:
    - name: "lexical_only"
      mode: "lexical_only"
      lexical:
        defType: "edismax"
        qf: "title^7 longDesc^2"
        pf: "title^20"
    - name: "vector_only"
      mode: "vector_only"
      knn:
        field: "emb"
        k: 100
        topK: 10
    - name: "hybrid_blend_70_30"
      mode: "hybrid"
      knn:
        field: "emb"
        k: 100
        topK: 10
      lexical:
        defType: "edismax"
        qf: "title^7 longDesc^2"
      blend:
        method: "normalize_linear" # linear | normalize_linear | rrf
        execution: "auto" # auto | client | solr_native
        weight_lexical: 0.7
        weight_vector: 0.3
        normalize: "zscore" # none | minmax | zscore
        missing_vector_score: 0.0
        missing_lexical_score: 0.0
        rrf_k: 60

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
  vector_hybrid:
    enabled: true
    topK: 10
    candidate_pool: 100
    sensitivity:
      enabled: true
      weights: [0.9, 0.7, 0.5, 0.3]

performance:
  enabled: true
  warmup:
    enabled: true
    iterations: 1
    strategy: "interleaved"
  capture:
    qtime: true
    client_latency: true
    percentiles: [50, 95, 99]
    per_query: true
  caches:
    enabled: true
    scope: "both"
    names: ["filterCache", "queryResultCache", "documentCache", "fieldValueCache"]
  index:
    enabled: true
    luke: true
    segment_info: true
    store_docvalues_heuristics: true

security:
  profile: "enterprise-safe" # local-dev | enterprise-safe | no-persist-sensitive | redacted-artifacts-only
  # optional external YAML file merged into this section:
  # config: "examples/security/basic_auth_env.yaml"
  baseline_auth:
    type: "none" # none | basic | bearer | mtls | plugin | kerberos
    # basic:
    # username_env: "SCHEMA_LENS_SOLR_USER"
    # password_env: "SCHEMA_LENS_SOLR_PASSWORD"
    # bearer:
    # token_env: "SCHEMA_LENS_SOLR_BEARER_TOKEN"
    # mtls:
    # cert_file: "./certs/client.pem"
    # key_file: "./certs/client.key"
    # ca_file: "./certs/ca.pem"
    # plugin/kerberos:
    # provider: "my_auth_plugin"
  shadow_auth:
    type: "none"
  audit:
    requested_by: "platform-team@example.com"
    approval_reference: "CR-12345"
  extra_sensitive_keys: ["session_id"]

observability:
  enabled: true
  prometheus:
    enabled: true
  otel:
    enabled: true
  webhooks:
    enabled: false
    urls:
      - "http://localhost:9000/schema-lens/events"
    timeout_seconds: 3.0
    headers:
      X-Schema-Lens-Source: "ci"

governance:
  enabled: true
  approval:
    requested_by: "search-platform@example.com"
    approved_by: "relevance-lead@example.com"
    ticket_id: "REL-421"
    change_request_id: "CR-9921"
  promotion_state: "stage" # dev | stage | prod_candidate | prod_approved
  policy_bundles:
    - "examples/governance/prod_promotion_policy.yaml"
  exceptions:
    - id: "ex-2026-001"
      rationale: "Temporary rollout exception"
      approved_by: "oncall@example.com"
      expiry: "2026-12-31T23:59:59Z"
  signing:
    enabled: true
    secret_env: "SCHEMA_LENS_GOV_SIGNING_KEY"

segments:
  enabled: true
  keys: ["tenant", "region", "locale", "catalog"]
  policy:
    rules:
      - segment_key: "tenant"
        segment_value: "acme"
        metric: "high_risk_percent"
        op: ">"
        value: 10
        severity: "fail"

privacy:
  profile: "default" # off | default | export-safe
  allowlist: ["summary", "diffs", "top_regressions"]
  denylist: ["raw_docs", "request_headers"]
  no_persist_sensitive: false
  hash_salt: "schema-lens-internal"
```

## Required fields

- `baseline.solr_url`
- `baseline.collection`
- `data.docs_source.path` when `data.docs_source.type=file`
- `data.docs_source.solr_url` and `data.docs_source.collection` when `data.docs_source.type=solr`
- `queries.source.path`
- `vector.scenarios` when `vector.enabled=true`
- `performance.capture.percentiles` must be a list of integers when present
- `security.profile` must be one of:
  - `local-dev`
  - `enterprise-safe`
  - `no-persist-sensitive`
  - `redacted-artifacts-only`

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
- `vector.enabled=true` enables scenario replay with `lexical_only` / `vector_only` / `hybrid`.
- Query JSONL supports:
  - `{\"params\": {...}, \"vector\": [...]}`.
  - `{\"json_request\": {...}, \"vector\": [...]}`.
- `evaluation.vector_hybrid` configures topK/candidate pool and optional sensitivity sweep.
- `performance.enabled=true` captures client latency, Solr `QTime`, cache deltas, and Luke-based
  index size heuristics into `perf_metrics.json`.
- `security.profile` controls artifact redaction and persistence of sampled docs/queries.
- `security.baseline_auth` and `security.shadow_auth` configure per-target auth material.
- Auth secrets can be provided inline or via `_env` / `_file` references.
- `audit.json` records requestor, approval reference, target cluster, and auth mode only.
- `observability.enabled=true` emits runtime events and webhook deliveries.
- `observability.prometheus.enabled=true` writes `prometheus_metrics.prom`.
- `observability.otel.enabled=true` records stage spans in `otel_spans.json`.
- `observability.webhooks.enabled=true` posts `run_started`, `run_completed`, and `drift_detected`
  events to configured URLs.
- `governance.enabled=true` requires at least `governance.approval.requested_by`.
- `governance.policy_bundles` supports reusable gate policy packs merged into a single bundle view.
- `governance.signing.enabled=true` records a deterministic `manifest_hash` and HMAC signature in
  run governance metadata.
- `segments.enabled=true` computes per-segment summaries into `segments.json`.
- Query JSONL can carry segment metadata in `segment`, or top-level keys like `tenant`/`region`.
- `privacy.profile=default|export-safe` enables deterministic masking and redaction on artifacts.
- `privacy.no_persist_sensitive=true` prunes sensitive raw artifacts after run completion.
- Performance gate rules can evaluate:
  - `p95_latency_regression_pct`
  - `p95_qtime_regression_pct`
  - `cache_eviction_regression_pct`
  - `index_size_regression_pct`
- If query vectors are missing and `vector.query_vector_policy=skip`, those query/scenario pairs
  are skipped with explicit reasons in replay outputs.
- `shadow.allow_shared_configset_fallback=true` allows non-isolated fallback only for plain
  configset clone path (no file patching).
- Empty `changes` is allowed with a warning.
