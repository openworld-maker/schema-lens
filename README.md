# SolrGuard

Search Change Governance for Apache Solr.

SolrGuard helps teams safely evaluate Solr schema/config/relevance changes with compatibility
detection, policy gates, approvals and exceptions, rollout planning, privacy-safe artifacts, and
operational integrations for CI/CD and platform workflows.

Current version: `v0.2.0`

SolrGuard is the new primary name. `schema-lens` remains available as a legacy CLI alias and
`schema_lens` remains the stable Python import path in this release.

## Quick value

- Detect Solr version and capability compatibility before rollout.
- Simulate and compare change impact with segment-aware risk views.
- Enforce policy gates with auditable approvals and time-bound exceptions.
- Produce privacy-safe, export-safe governance artifacts.
- Integrate with CI/CD, observability, Docker, Helm, and API service mode.

## Start here

- One-command local evaluator:
  - `./scripts/first_time_evaluator.sh`
- [Quickstart](#quickstart-basic)
- [Enterprise quickstart](#quickstart-enterprise-governance-mode)
- [Compatibility matrix](docs/enterprise/compatibility-matrix.md)
- [Governance guide](docs/enterprise/policies.md)
- [Deployment guide](docs/deployment.md)
- [Example outputs](docs/example-outputs.md)
- [Roadmap](docs/roadmap.md)
- [Examples index](examples/README.md)
- [Docs index](docs/README.md)

## Formerly Schema-Lens

- `solrguard` is now the primary CLI and product name.
- `schema-lens` remains available as a legacy CLI alias for backward compatibility.
- Internal Python import path remains `schema_lens` in this release to minimize migration risk.

## Table of contents

- [What is SolrGuard?](#what-is-solrguard)
- [Why it exists](#why-it-exists)
- [Why SolrGuard](#why-solrguard)
- [Who is it for?](#who-is-it-for)
- [Enterprise evaluation workflow](#enterprise-evaluation-workflow)
- [Safe Evaluation In Enterprise Solr Environments](#safe-evaluation-in-enterprise-solr-environments)
- [Feature matrix](#feature-matrix)
- [Core capabilities](#core-capabilities)
- [Advanced features](#advanced-features)
- [End-to-end flow](#end-to-end-flow)
- [Requirements](#requirements)
- [Usage guide](#usage-guide)
- [Quickstart (basic)](#quickstart-basic)
- [Quickstart (synonym rewrite impact)](#quickstart-synonym-rewrite-impact)
- [Quickstart (vector and hybrid simulation)](#quickstart-vector-and-hybrid-simulation)
- [Quickstart (enterprise governance mode)](#quickstart-enterprise-governance-mode)
- [CLI reference](#cli-reference)
- [Compatibility and Migration](#compatibility-and-migration)
- [Changeset reference](#changeset-reference)
- [Output artifacts](#output-artifacts)
- [Plugin SDK](#plugin-sdk)
- [Security Mode](#security-mode)
- [Solr Compatibility](#solr-compatibility)
- [Enterprise Compatibility Contract](#enterprise-compatibility-contract)
- [API Server Mode](#api-server-mode)
- [Observability](#observability)
- [Governance](#governance)
- [Rollout Orchestration](#rollout-orchestration)
- [Segment-Aware Analysis](#segment-aware-analysis)
- [Data Privacy](#data-privacy)
- [Enterprise Packaging](#enterprise-packaging)
- [Quality gate and CI usage](#quality-gate-and-ci-usage)
- [Architecture](#architecture)
- [Documentation map](#documentation-map)
- [Examples map](#examples-map)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Safety notes](#safety-notes)

## What is SolrGuard?

SolrGuard is a local-first governance toolkit for safe Solr change evaluation and rollout decisions.
It combines simulation, compatibility checks, policy controls, and operational artifacts so teams can
move faster without losing release safety.

## Why it exists

Schema/analyzer/query-default changes can silently degrade relevance. Teams need a reproducible
way to answer:

1. What changed in ranking quality?
2. Which queries/documents were impacted?
3. Did parser/rewrite behavior change (synonyms, clause shape, mm pressure)?
4. Should CI block rollout?

SolrGuard provides this as a local-first CLI workflow.

## Why SolrGuard

- deterministic governance artifacts for release decisions
- compatibility and fallback visibility before rollout
- policy-as-code + CI gate integration
- auditable approvals/exceptions/promotion metadata
- security/privacy controls suitable for enterprise traffic data
- rollout verification and post-cutover checks for release safety
- operational telemetry for SRE and platform governance workflows

## Who is it for?

- Relevance engineers: quantify ranking/query parser impact before production rollout.
- Solr platform owners: enforce compatibility and policy contracts across environments.
- SRE and release managers: gate deployments with auditable risk, rollback, and verification artifacts.
- Enterprise architecture/governance teams: enforce approval and exception controls with traceability.
- Consulting and migration teams: standardize Solr 8/9/10 readiness evaluation workflows.

## Enterprise evaluation workflow

```text
1) Detect target version/capabilities
2) Compare baseline vs candidate behavior
3) Evaluate policy bundle
4) Attach approvals/exceptions metadata
5) Generate export-safe governance artifacts
6) Produce rollout + rollback plan
7) Verify post-cutover state
```

## Safe Evaluation In Enterprise Solr Environments

Governance workflow (high-level):

```text
Change Proposal
   -> Secure Simulation (shadow replay + compatibility detection)
   -> Policy Evaluation (global + segment-aware)
   -> Approval/Exception Metadata
   -> Rollout Plan (canary/alias/rollback)
   -> Post-cutover Verification
```

## Feature matrix

| Capability | Available | Notes | Enterprise relevance |
|---|---|---|---|
| Solr version detection | Yes | Solr 8/9 + forward-ready unknown handling | Prevents unsafe assumptions |
| Capability detection | Yes | Flags support/degraded fallback paths | Explains why behavior differs |
| Schema/config comparison | Yes | Replay/compare with ranking + non-ranking diff metrics | Core release risk evidence |
| Policy evaluation | Yes | YAML policy bundles and gate evaluator | Deterministic pass/fail in CI |
| Approvals/exceptions | Yes | Approver metadata + expiring exceptions | Auditable governance controls |
| Security mode | Yes | Basic/Bearer/mTLS + redaction/no-sensitive mode | Safer enterprise execution |
| Privacy-safe artifacts | Yes | Masking/hashing/export-safe summaries | Compliance-oriented sharing |
| Segment-aware reporting | Yes | Tenant/region/locale grouping and ranking | Detects localized regressions |
| Prometheus metrics | Yes | `solrguard_*` primary + legacy aliases | SRE visibility |
| OpenTelemetry traces | Yes | Stage-level spans without secret leakage | Production troubleshooting |
| Webhook notifications | Yes | Run/gate event delivery with retries | External orchestration integration |
| GitOps rollout planning | Yes | Diff/canary/alias-swap/rollback plans | Safer production promotions |
| Docker deployment | Yes | Runtime image and deployment docs | Portable runtime |
| Helm deployment | Yes | `helm/solrguard` primary chart path | Cluster operations ready |
| API server mode | Yes | Run/status/artifact endpoints | Dashboard and portal integration |

## Core capabilities

- SolrCloud shadow provisioning via Collections API.
- Configset-aware shadow runs:
  - clone/download baseline configset
  - patch `synonyms.txt` / `stopwords.txt`
  - upload isolated patched configset
  - create shadow with `collection.configName=<patched>`
- Changeset ops:
  - `schema.field.update`
  - `schema.fieldType.replace`
  - `schema.analyzer.remove_filter`
  - `schema.synonym.update`
  - `schema.stopwords.update`
  - `queryparams.set`
- Query replay metrics:
  - `Overlap@K`, `Jaccard@K`, `Kendall Tau@K`
- Diff dimensions:
  - ranking movement/new/dropped docs
  - `numFound` deltas (filter/docset impact)
  - facet count diffs
  - top-K sort instability ratio
- Explain capture:
  - classic debug explain
  - structured explain mode
- Query rewrite impact simulation:
  - capture parsed query debug (`parsedquery`, `parsedquery_toString`)
  - clause count + clause delta
  - term added/removed heuristics
  - synonym expansion hints
  - rewrite risk flags:
    - `REWRITE_CLAUSE_SPIKE`
    - `SYNONYM_EXPANSION_CHANGED`
    - `PARSED_QUERY_SHAPE_CHANGED`
- Vector and hybrid ranking simulation:
  - scenario modes: `lexical_only`, `vector_only`, `hybrid`
  - query input supports `params` and `json_request`
  - vector similarity sanity checks (field, dimension, similarity)
  - vector retrieval stability metrics and semantic churn
  - client-side hybrid blending (`linear`, `normalize_linear`, `rrf`) with Solr-native fallback
  - lexical vs vector contribution estimates with dominance/confidence labels
  - optional weight sensitivity sweep and tipping-point detection
- Query sourcing:
  - file (`simple`, `jsonl`)
  - log extraction with sanitization and sampling
- Doc sourcing:
  - file (`jsonl`, `json`)
  - Solr `/export` with cursorMark fallback
- Reproducibility:
  - baseline snapshot hashing
  - run manifest with inputs/settings/hash references
- CI readiness:
  - policy-based gate command
  - markdown summary for PR comments/checks

## Advanced features

### 1) Synonym/stopwords configset simulation

Use `schema.synonym.update` / `schema.stopwords.update` to patch shadow configset files and
validate impact before rollout.

Example:

```yaml
shadow:
  baseline_configset_dir: "examples/configsets/procurement_v1"
  promote_uploaded_configset_trusted: true

changes:
  - op: "schema.synonym.update"
    mode: "replace"
    source_file: "examples/synonyms/procurement_synonyms_v2.txt"
    target:
      files:
        - path: "conf/synonyms.txt"
  - op: "schema.stopwords.update"
    mode: "patch_merge"
    source_file: "examples/stopwords/procurement_stopwords_v2.txt"
    target:
      files:
        - path: "conf/stopwords.txt"
```

Notes:

- In SolrCloud environments where uploaded configsets are untrusted, solrguard can promote the
  uploaded configset to a trusted clone (`promote_uploaded_configset_trusted: true`, default).
- `target.files[].path` supports both `conf/<file>` and root configset style where applicable.

### 2) Query rewrite impact simulation

Enable rewrite parsing diffs for risky queries:

```yaml
evaluation:
  rewrite_diff:
    enabled: true
    max_queries: 25
    debug_mode: "results"
    clause_spike_threshold: 2
    always_for_high_risk: true
```

Reported outputs include:

- baseline vs shadow parsed queries
- clause count/delta
- added/removed terms
- synonym hints
- rewrite risk flags (`REWRITE_CLAUSE_SPIKE`, `SYNONYM_EXPANSION_CHANGED`,
  `PARSED_QUERY_SHAPE_CHANGED`)

If `debug=results` does not include parsed query fields on your Solr setup, solrguard
automatically falls back to `debugQuery=true` for rewrite extraction.

### 3) Production realism bundle

- `queries.source.type=log` for real traffic extraction + sanitization/sampling.
- `data.docs_source.type=solr` for export/cursorMark sampling.
- `preflight` schema dependency safety findings in `schema_risk.json`.
- `gate` + `ci summarize` for rollout policy enforcement in CI.

### 4) Vector and hybrid simulation

Enable vector-aware scenarios in changeset:

```yaml
vector:
  enabled: true
  field: "emb"
  dimension: 8
  similarity: "cosine"
  query_vector_policy: "skip" # skip|fail
  scenarios:
    - name: "lexical_only"
      mode: "lexical_only"
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
      blend:
        method: "normalize_linear" # linear|normalize_linear|rrf
        execution: "client" # auto|client|solr_native
        weight_lexical: 0.7
        weight_vector: 0.3
        normalize: "zscore"

evaluation:
  vector_hybrid:
    enabled: true
    topK: 10
    candidate_pool: 100
    sensitivity:
      enabled: true
      weights: [0.9, 0.7, 0.5, 0.3]
```

Run-time overrides:

- `--scenario <name>` (repeatable)
- `--enable-sensitivity/--no-enable-sensitivity`
- `--weights \"0.9,0.7,0.5,0.3\"`
- `--vector-dimension-override 8` (debug/testing)

### 5) Performance and cost impact

Enable performance capture to estimate latency, cache churn, and index-footprint impact:

```yaml
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
  caches:
    enabled: true
    names: ["filterCache", "queryResultCache", "documentCache", "fieldValueCache"]
  index:
    enabled: true
    luke: true
```

Outputs include `perf_metrics.json`, grouped query classes, cache deltas, index-size deltas, and
report callouts such as p95 latency regressions.

### 6) Deterministic diagnosis and recommendations

SolrGuard can convert diff evidence into deterministic root-cause findings and action-oriented
next steps:

- root causes:
  - `PREFIX_MATCHING_REMOVED`
  - `TITLE_BOOST_REDUCED`
  - `MIN_SHOULD_MATCH_STRICTER`
  - `ANALYSIS_REMOVED_OR_FIELD_EXACTIFIED`
  - `VECTOR_DOMINANCE_INCREASED`
  - `CACHE_OR_LATENCY_REGRESSION`
  - `FACET_FIELD_BEHAVIOR_CHANGED`
- recommendations:
  - dual-field prefix strategy
  - copyField migration path
  - smaller boost/mm steps
  - hybrid weight sweeps
  - cache/docValues tuning

These are rules-based. There is no LLM dependency.

### 7) Environment compare, monitoring, dashboard, and LTR

- `compare-env` compares two live Solr environments for ranking/perf drift.
- `monitor` appends snapshot-vs-current drift summaries into `monitor_history.jsonl`.
- `serve` exposes a read-only FastAPI dashboard over run artifacts.
- `ltr` awareness detects LTR requests and diffs feature logs when `[features]` is available.

## End-to-end flow

```text
changeset.yaml + docs + queries
          |
          v
validate -> snapshot/inspect -> schema preflight
          |
          v
create shadow (isolated configset clone/patch when needed)
          |
          v
index docs (file or Solr sampled)
          |
          v
replay baseline vs shadow
          |
          v
compare (ranking + facets + filter + sort)
          |
          v
rewrite diff + optional explain bundles
          |
          v
report.json + report.html + run artifacts
```

## Requirements

- Python `3.11+`
- Solr reachable over HTTP
- Docker + Docker Compose for local smoke/demo

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage guide

Start with [docs/usage-guide.md](docs/usage-guide.md).

It provides:

- the easiest first-time local workflow
- a capability map by job-to-be-done
- command selection guidance
- example commands for schema, rewrite, vector, perf, env compare, dashboard, and monitoring
- artifact-reading guidance
- current validation status for each feature area

## Quickstart (basic)

1. Start local SolrCloud:

```bash
make dev-up
```

2. Create baseline `products` collection and index sample docs:

```bash
make demo-setup
```

3. Run solrguard:

```bash
solrguard run examples/changesets/fieldtype-change.yaml --out out/demo
```

4. Inspect output:

```bash
cat out/demo/report.json
open out/demo/report.html
```

## Quickstart (synonym rewrite impact)

This scenario simulates a production-style synonym/stopword configset update and captures rewrite
parser diffs.

1. Start SolrCloud:

```bash
make dev-up
```

2. Prepare procurement baseline collection/configset:

```bash
make demo-setup-procurement
```

3. Run rewrite-impact changeset:

```bash
solrguard run examples/changesets/procurement-synonym-rewrite.yaml --out out/procurement_demo
```

4. Validate rewrite flags:

```bash
cat out/procurement_demo/compare.json | rg "SYNONYM_EXPANSION_CHANGED|REWRITE_CLAUSE_SPIKE"
```

## Quickstart (vector and hybrid simulation)

1. Start SolrCloud:

```bash
make dev-up
```

2. Prepare vector collection/configset and ingest embeddings:

```bash
make demo-setup-vector
```

3. Run vector/hybrid scenario pack:

```bash
solrguard run examples/changesets/vector-hybrid-demo.yaml --out out/vector_demo --enable-sensitivity
```

4. Inspect vector outputs:

```bash
cat out/vector_demo/compare.json | rg "vector_hybrid|hybrid_sensitivity|dominance"
cat out/vector_demo/hybrid_sensitivity.json
open out/vector_demo/report.html
```

## Quickstart (enterprise governance mode)

1. Validate enterprise changeset:

```bash
solrguard validate examples/enterprise/governance/prod_promotion_changeset.yaml
```

2. Run governance simulation:

```bash
solrguard run examples/enterprise/governance/prod_promotion_changeset.yaml --out out/enterprise_demo
```

3. Evaluate release policy:

```bash
solrguard gate --compare out/enterprise_demo/compare.json --policy examples/policy/perf_gate_default.yaml
```

4. Inspect compatibility contract:

```bash
solrguard detect-capabilities --from-file examples/compat/solr9_system_info.json
solrguard compatibility --from-file examples/compat/solr9_system_info.json
```

## CLI reference

### Primary commands

- `solrguard validate <changeset.yaml>`
- `solrguard inspect --solr-url URL --collection NAME --out PATH`
- `solrguard snapshot --solr-url URL --collection NAME --out DIR`
- `solrguard run <changeset.yaml> --out DIR [--snapshot DIR] [--k K] [--cleanup/--no-cleanup] [--scenario NAME ...] [--enable-sensitivity/--no-enable-sensitivity] [--weights CSV] [--vector-dimension-override INT]`
- `solrguard replay --baseline-solr-url ... --baseline-collection ... --shadow-solr-url ... --shadow-collection ... --queries ... --k ... --out ...`
- `solrguard compare --replay PATH --k K --out PATH`
- `solrguard report --compare PATH --manifest PATH --out DIR`
- `solrguard detect-capabilities --solr-url URL | --from-file system_info.json`
- `solrguard compatibility --target URL | --from-file system_info.json`
- `solrguard api serve --data-dir .solrguard_api --host 127.0.0.1 --port 8080`

### Shadow lifecycle

- `solrguard shadow create <changeset.yaml> --out shadow.json`
- `solrguard shadow index --shadow shadow.json --docs docs.jsonl`

### Query/doc source tooling

- `solrguard queries extract --from <logfile> --out <queries.jsonl> [--max N] [--sample top|reservoir] [--seed INT] [--sanitize/--no-sanitize]`
- `solrguard docs sample --solr-url URL --collection NAME --mode export|cursormark --query "*:*" --fl "*" --sort "id asc" --sample-n N --batch-size N --out PATH`

### Golden + CI helpers

- `solrguard golden add --q "..." --expect-id DOC123 --out golden.jsonl`
- `solrguard golden discover --from queries.jsonl --top 50 --out golden.jsonl`
- `solrguard gate --compare compare.json --policy policy.yaml`
- `solrguard ci summarize --compare compare.json --out summary.md [--policy policy.yaml]`

### Analysis and operations helpers

- `solrguard recommend --run out/run_xxx --out out/recommendations.json`
- `solrguard compare-env --env1 examples/envs/prod_us.yaml --env2 examples/envs/prod_eu.yaml --queries examples/queries/env_compare_queries.jsonl --out out/env_compare`
- `solrguard serve --run out/demo --port 8080`
- `solrguard serve --compare out/env_compare/compare.json --port 8080`
- `solrguard serve --api-url http://127.0.0.1:8090 --run-id <id> --port 8080`
- `solrguard monitor --baseline-snapshot out/demo --queries examples/queries/env_compare_queries.jsonl --out out/monitor`
- `solrguard rollout git-drift --solr-url URL --collection NAME --local-configset-dir DIR --out drift.json`
- `solrguard rollout canary-plan --baseline-collection NAME --canary-collection NAME --out canary_plan.json`
- `solrguard rollout alias-swap-plan --alias NAME --from-collection SRC --to-collection DST --out alias_plan.json [--execute --solr-url URL]`
- `solrguard rollout rollback-plan --alias NAME --previous-collection SRC --out rollback_plan.json`
- `solrguard rollout verify-post-cutover --canary-compare canary_compare.json --prod-compare prod_compare.json --out verify.json`

## Compatibility and Migration

Backward compatibility in this release:

- `schema-lens` CLI alias is retained and maps to `solrguard`.
- internal Python package path remains `schema_lens`.
- preferred changeset key is `solrguard_version`; legacy `schema_lens_version` is retained.
- legacy API auth header `x-schema-lens-token` is still accepted; preferred header is `x-solrguard-token`.
- legacy Prometheus metrics `schema_lens_*` are retained; `solrguard_*` is primary.
- legacy Helm chart path `helm/schema-lens` is retained; `helm/solrguard` is primary.

Recommended migration path:

1. Switch scripts and CI jobs from `schema-lens` to `solrguard`.
2. Keep existing imports unchanged for now (`schema_lens`).
3. Move changesets to `solrguard_version` key.
4. Track migration/deprecation timelines:
   - [`docs/migration-from-schema-lens.md`](docs/migration-from-schema-lens.md)
   - [`docs/deprecation-schedule.md`](docs/deprecation-schedule.md)
   - [`docs/major-version-module-migration.md`](docs/major-version-module-migration.md)

## Changeset reference

See [docs/changeset-spec.md](docs/changeset-spec.md).

Notable v0.2.0 additions:

- `schema.synonym.update`
- `schema.stopwords.update`
- `evaluation.rewrite_diff`
- `vector` scenarios + `evaluation.vector_hybrid`
- optional `shadow.baseline_configset_dir` for local configset source when patching.

## Output artifacts

A full `run` emits a reproducible bundle under `--out`:

- `run_manifest.json`
- `inspect.json`
- `snapshot.json`
- `snapshot.schema.json`
- `snapshot.system.json`
- `snapshot.collection.json`
- `snapshot.hash.txt`
- `compat.json`
- `schema_risk.json`
- `shadow.json`
- `docs_sample.jsonl` (when Solr doc sampling enabled)
- `queries_extracted.jsonl` (when log extraction enabled)
- `replay.json`
- `replay_<scenario>.json` (when vector scenarios enabled)
- `compare.json`
- `vector_validation.json` (when vector enabled)
- `hybrid_sensitivity.json` (when enabled)
- `perf_metrics.json` (when performance enabled)
- `segments.json` (when segment analysis enabled)
- `rootcauses.json`
- `recommendations.json`
- `env_compare.json` (for `compare-env`)
- `ltr_impact.json`
- `audit.json` (security profile + auth mode trail)
- `governance.json` (approval/promotion/exception/signing metadata)
- `privacy.json` (masking, suppression, retention summary)
- `observability_events.jsonl` / `otel_spans.json` / `webhook_deliveries.json` (when enabled)
- `prometheus_metrics.prom` (when Prometheus export enabled)
- `plugins.json` (when plugin SDK is enabled)
- `latest_monitor.json` / `monitor_history.jsonl` (for `monitor`)
- `report.json`
- `report.html`

`compare.json` and reports include additive sections for rewrite impact, vector/hybrid simulation,
performance, root-cause analysis, recommendations, environment drift, and LTR when available.

## Plugin SDK

Plugin support is optional and config-driven. Enable it in the changeset:

```yaml
plugins:
  enabled: true
  directories:
    - "./examples/plugins"
  load_builtin: true
  enabled_plugins:
    - sample_query_source
    - sample_gate
    - sample_report
  strict_mode: false
  config:
    sample_query_source:
      path: "examples/querylogs/procurement_queries_custom.json"
    sample_gate:
      overlap_threshold: 0.5
      failure_pct: 30
    sample_report:
      group_by: "tenant"
```

Supported extension-point contracts include:

- auth providers
- query sources
- document sources
- replay executors
- diff analyzers
- root-cause and recommendation rules
- gate evaluators
- report renderers/widgets
- rollout providers
- observability exporters

Plugin loading supports:

- built-in plugins (`plugins.load_builtin`)
- local plugin paths (`plugins.directories`)
- Python entry points (`schema_lens.plugins`)
- explicit activation (`plugins.enabled_plugins`)

Lifecycle hooks:

1. `validate()`
2. `initialize()`
3. `execute()`
4. `cleanup()`

Compatibility/versioning policy:

- Plugins declare `compatible_schema_lens_version` in metadata (`schema_lens_version` is still accepted).
- Incompatible plugins are skipped and reported in `plugins.json`.
- `plugins.strict_mode: true` turns plugin load/compat/execute errors into run-blocking failures.

Plugin runtime artifacts:

- `out/<run>/plugins/<plugin_name>/result.json`
- `out/<run>/plugins/<plugin_name>/debug.json`
- `out/<run>/plugins/<plugin_name>/notes.txt`
- `plugins.json`, `compare.json.plugins`, and `report.json.plugin_report_sections`

Plugin CLI:

- `solrguard plugins list --changeset examples/changesets/plugin-sdk-demo.yaml`
- `solrguard plugins validate --changeset examples/changesets/plugin-sdk-demo.yaml`
- `solrguard plugins inspect sample_gate --changeset examples/changesets/plugin-sdk-demo.yaml`

Developer guide and examples:

- [docs/plugin_sdk.md](docs/plugin_sdk.md)
- `examples/plugins/sample_query_source/`
- `examples/plugins/sample_gate/`
- `examples/plugins/sample_report/`

## Security Mode

Security controls are optional and backward compatible. Configure under `security` in a changeset:

```yaml
security:
  profile: enterprise-safe
  baseline_auth:
    type: basic
    username_env: SCHEMA_LENS_SOLR_USER
    password_env: SCHEMA_LENS_SOLR_PASSWORD
  shadow_auth:
    type: bearer
    token_env: SCHEMA_LENS_SOLR_TOKEN
  audit:
    requested_by: "user@example.com"
    approval_reference: "CR-12345"
```

Supported auth modes:

- `none`
- `basic` (inline, `_env`, `_file`)
- `bearer` (inline, `_env`, `_file`)
- `mtls` (`cert_file`, optional `key_file`, optional `ca_file`)
- `plugin` / `kerberos` (via auth provider plugin)

Security profiles:

- `local-dev`
- `enterprise-safe`
- `no-persist-sensitive`
- `redacted-artifacts-only`

Behavior:

- secrets are redacted from `run_manifest.json`, `compare.json`, and `report.json` when redaction is enabled
- `Authorization` headers are always masked in stored payloads
- `audit.json` records requester, approval reference, target cluster/collection, and auth mode (never secret values)

Examples:

- `examples/security/basic_auth_env.yaml`
- `examples/security/bearer_token_env.yaml`
- `examples/security/mtls_config.yaml`

## Solr Compatibility

`solrguard` detects Solr version from `/admin/info/system` and records capabilities in
`compat.json` and `run_manifest.json`.

Supported compatibility targets:

- Solr `8.x`
- Solr `9.x`
- Solr `10.x`

Capability-driven fallbacks:

- vector/hybrid simulation is skipped when `vector_query_supported=false`
- structured explain falls back to classic explain when unsupported
- performance metrics capture is disabled when metrics capability is unavailable

Reference fixtures:

- `examples/compat/solr8_system_info.json`
- `examples/compat/solr9_system_info.json`
- `examples/compat/solr10_system_info.json`

Compatibility CLI:

```bash
solrguard detect-capabilities --solr-url http://localhost:8983/solr
solrguard compatibility --target http://localhost:8983/solr
```

## Enterprise Compatibility Contract

- deterministic capability flags with explicit `missing_capabilities`
- support-tier framing (`supported_with_fallbacks`, `recommended`, `forward_ready`, `unknown`)
- fallback reporting with human-readable actions
- fixture-driven tests for Solr 8/9/10 payloads

See:

- [docs/compatibility.md](docs/compatibility.md)
- [docs/enterprise/compatibility-matrix.md](docs/enterprise/compatibility-matrix.md)

## API Server Mode

Run a local-first REST service:

```bash
solrguard api serve --data-dir .solrguard_api --host 127.0.0.1 --port 8080
```

Optional enterprise-oriented runtime modes:

```bash
solrguard api serve \
  --job-store sqlite \
  --sqlite-path .solrguard_api/jobs.db \
  --worker-mode external
```

Core endpoints:

- `GET /health`
- `GET /health/details`
- `GET /capabilities`
- `GET /plugins`
- `POST /runs`
- `GET /runs`
- `GET /runs/{job_id}`
- `GET /runs/{job_id}/summary`
- `POST /compare-env`
- `GET /compare-env/{job_id}`
- `POST /gates`
- `GET /gates/{job_id}`
- `GET /artifacts/{job_id}`
- `GET /artifacts/{job_id}/{artifact_name}`
- compatibility: `POST /gate`, `GET /runs/{job_id}/artifacts/*`

Create a run:

```bash
curl -sS -X POST http://127.0.0.1:8080/runs \
  -H "content-type: application/json" \
  -d @examples/api/create_run_from_path.json
```

Create a run from inline changeset:

```bash
curl -sS -X POST http://127.0.0.1:8080/runs \
  -H "content-type: application/json" \
  -d @examples/api/create_run_inline.json
```

Compare environments:

```bash
curl -sS -X POST http://127.0.0.1:8080/compare-env \
  -H "content-type: application/json" \
  -d @examples/api/compare_env_request.json
```

Gate evaluation:

```bash
curl -sS -X POST http://127.0.0.1:8080/gates \
  -H "content-type: application/json" \
  -d @examples/api/gate_request.json
```

Dashboard integration:

```bash
solrguard serve --api-url http://127.0.0.1:8080 --run-id <run-id> --port 8080
```

Inspect storage and runtime config:

```bash
solrguard api inspect --data-dir .solrguard_api
```

Local-first security:

- service defaults to local-only mode
- pluggable auth provider + RBAC policy hooks are supported in app factory wiring
- request audit trail is written to `.solrguard_api/logs/api_audit.jsonl`
- secrets are redacted in stored request snapshots for obvious credential fields
- artifacts are served only by tracked job/artifact mappings (path traversal protected)

Additional docs:

- `docs/api_server.md`
- `docs/roadmap_api_server.md`
- `docs/compatibility.md`
- `docs/enterprise/README.md`
- `docs/migration-from-schema-lens.md`
- `docs/brand-positioning.md`
- `docs/release-notes-solrguard.md`
- `docs/deprecation-schedule.md`
- `docs/major-version-module-migration.md`
- `docs/enterprise/security.md`
- `docs/enterprise/compatibility-matrix.md`
- `docs/enterprise/observability.md`
- `docs/enterprise/policies.md`
- `docs/enterprise/approvals-and-exceptions.md`
- `docs/enterprise/gitops.md`
- `docs/enterprise/segmentation.md`
- `docs/enterprise/privacy.md`
- `docs/enterprise/deployment.md`

## Observability

Enable runtime observability in changeset config:

```yaml
observability:
  enabled: true
  prometheus:
    enabled: true
  otel:
    enabled: true
  webhooks:
    enabled: true
    urls:
      - "http://localhost:9000/solrguard/events"
```

Runtime events emitted:

- `run_started`
- `run_completed`
- `drift_detected`
- `gate_failed` (reserved for gate workflows)

Prometheus output includes:

- `solrguard_runs_total`
- `solrguard_runs_failed_total`
- `solrguard_high_risk_queries_total`
- `solrguard_gate_failures_total`
- `solrguard_p95_latency_regression_pct`
- `solrguard_cache_eviction_regression_pct`

Legacy metric names with `schema_lens_*` prefix are also emitted for backward compatibility.

Examples:

- `examples/observability/prometheus_config.md`
- `examples/observability/webhook_payload.json`
- `examples/observability/grafana_dashboard.json`

## Governance

Governance is optional and policy-driven:

```yaml
governance:
  enabled: true
  approval:
    requested_by: "search-platform@example.com"
    ticket_id: "REL-421"
  promotion_state: "stage" # dev|stage|prod_candidate|prod_approved
  policy_bundles:
    - "./examples/governance/prod_promotion_policy.yaml"
  exceptions:
    - id: "ex-2026-001"
      rationale: "Temporary rollout exception"
      expiry: "2026-12-31T23:59:59Z"
  signing:
    enabled: true
    secret_env: "SCHEMA_LENS_GOV_SIGNING_KEY"
```

Behavior:

- validates approval metadata and promotion state
- validates exception records with expiry tracking
- merges reusable policy bundles for downstream gate workflows
- writes `governance.json`
- records `manifest_hash` and optional `signature` in manifest governance settings

Examples:

- `examples/governance/prod_promotion_policy.yaml`
- `examples/governance/approval_metadata.json`
- `examples/governance/exception_record.json`

## Rollout Orchestration

Rollout tooling is dry-run by default and emits deterministic JSON plans.

Supported flows:

- Git configset drift detection against live cluster
- canary rollout checklist generation
- alias swap plan generation
- rollback plan generation
- post-cutover verify checks

Example commands:

```bash
solrguard rollout git-drift \
  --solr-url http://localhost:8983/solr \
  --collection products \
  --local-configset-dir examples/configsets/procurement_v1 \
  --out out/rollout/git_drift.json

solrguard rollout canary-plan \
  --baseline-collection products \
  --canary-collection products_canary \
  --traffic-sample-ratio 0.1 \
  --replay-query-count 500 \
  --out out/rollout/canary_plan.json

solrguard rollout alias-swap-plan \
  --alias products_live \
  --from-collection products_v1 \
  --to-collection products_v2 \
  --out out/rollout/alias_swap_plan.json
```

Execute mode is opt-in and explicitly dangerous:

- `solrguard rollout alias-swap-plan ... --execute --solr-url URL`

Examples:

- `examples/rollout/git_configset_compare.yaml`
- `examples/rollout/canary_plan.yaml`
- `examples/rollout/alias_swap_plan.json`

## Segment-Aware Analysis

Schema-lens can aggregate replay/compare impact by segment keys such as:

- `tenant`
- `region`
- `locale`
- `catalog`
- arbitrary labels in `segment` metadata

Use segmented query input (JSONL):

- `examples/queries/multitenant_queries.jsonl`

Optional segment config in changeset:

```yaml
segments:
  enabled: true
  keys: ["tenant", "region", "locale", "catalog"]
  policy:
    rules:
      - segment_key: tenant
        segment_value: acme
        metric: high_risk_percent
        op: ">"
        value: 10
        severity: fail
```

Outputs:

- `segments.json` with `by_segment`, `top_impacted`, and policy evaluation
- `compare.json.segments`
- `report.json.segments`

Example policy:

- `examples/policy/tenant_specific_policy.yaml`

## Data Privacy

Privacy controls are optional and deterministic.

```yaml
privacy:
  profile: export-safe # off | default | export-safe
  allowlist: ["summary", "diffs", "top_regressions"]
  denylist: ["raw_docs", "request_headers"]
  no_persist_sensitive: true
  hash_salt: "internal-salt"
```

Capabilities:

- email masking
- UUID masking
- numeric ID hashing
- allowlist/denylist filtering
- raw sample suppression via profile
- retention pruning for sensitive artifacts

Outputs:

- `privacy.json`
- redacted `compare.json` / `report.json` / `run_manifest.json` when enabled

Examples:

- `examples/privacy/pii_masking_profile.yaml`
- `examples/privacy/export_safe_mode.yaml`

## Enterprise Packaging

Distribution targets included:

- Python package (build with `python -m build`)
- Docker image (`docker/Dockerfile`)
- Helm chart (`helm/solrguard`)
- release workflow (`.github/workflows/release.yml`)

Release scripts:

- `scripts/release/build_release.sh` (build + checksum + SBOM placeholder)
- `scripts/release/verify_reproducibility.sh` (checksum verification)

Deployment examples:

- `examples/deploy/docker_run.md`
- `examples/deploy/k8s_job.yaml`
- `examples/deploy/github_actions.yml`

## Quality gate and CI usage

Run policy gate:

```bash
solrguard gate --compare out/demo/compare.json --policy examples/policy/gate_default.yaml
```

Exit codes:

- `0`: pass
- `2`: policy fail
- `1`: runtime/config error

Generate PR-friendly markdown summary:

```bash
solrguard ci summarize --compare out/demo/compare.json --policy examples/policy/gate_default.yaml --out out/demo/summary.md
```

GitHub Actions workflows included:

- `.github/workflows/ci.yml` (lint + unit + relevance summary job)
- `.github/workflows/smoke-matrix.yml` (manual matrix run)

## Architecture

See [docs/architecture.md](docs/architecture.md) for the package map, stage flow, artifact model,
and extension rules for new tracks.

## Documentation map

- Getting started: [docs/usage-guide.md](docs/usage-guide.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Compatibility: [docs/compatibility.md](docs/compatibility.md)
- Security: [docs/enterprise/security.md](docs/enterprise/security.md)
- Governance: [docs/enterprise/policies.md](docs/enterprise/policies.md)
- Rollout: [docs/enterprise/gitops.md](docs/enterprise/gitops.md)
- Observability: [docs/enterprise/observability.md](docs/enterprise/observability.md)
- Privacy: [docs/enterprise/privacy.md](docs/enterprise/privacy.md)
- Deployment: [docs/deployment.md](docs/deployment.md)
- Migration: [docs/migration-from-schema-lens.md](docs/migration-from-schema-lens.md)
- Full docs index: [docs/README.md](docs/README.md)

## Examples map

- Changeset quick eval examples: `examples/changesets/`
- API requests: `examples/api/`
- Security mode examples: `examples/security/` and `examples/enterprise/security/`
- Governance policy and approval examples: `examples/governance/` and `examples/enterprise/governance/`
- Rollout orchestration examples: `examples/rollout/` and `examples/enterprise/gitops/`
- Observability examples: `examples/observability/` and `examples/enterprise/observability/`
- Privacy/export-safe examples: `examples/privacy/` and `examples/enterprise/privacy/`
- Deployment examples: `examples/deploy/` and `examples/enterprise/deployment/`
- Full examples index: [examples/README.md](examples/README.md)

## Testing

Fast checks:

```bash
ruff check .
pytest -q -m "not integration"
```

Full local smoke matrix:

```bash
make smoke-matrix
```

Vector-focused smoke:

```bash
make smoke-vector
```

Performance example:

```bash
.venv/bin/solrguard run examples/changesets/perf_estimator_example.yaml --out out/perf_demo
.venv/bin/solrguard gate --compare out/perf_demo/compare.json --policy examples/policy/perf_gate_default.yaml
```

Environment compare example:

```bash
.venv/bin/solrguard compare-env \
  --env1 examples/envs/prod_us.yaml \
  --env2 examples/envs/prod_eu.yaml \
  --queries examples/queries/env_compare_queries.jsonl \
  --out out/env_compare
```

Integration-marked tests:

```bash
RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration
```

### Validation status

End-to-end smoke coverage currently exists for:

- base `run` workflow
- rewrite diff workflow
- vector/hybrid workflow
- smoke-matrix orchestration
- environment compare workflow
- monitor workflow
- serve dashboard workflow

These are covered by:

- `tests/integration/test_run_smoke.py`
- `tests/integration/test_rewrite_diff_smoke.py`
- `tests/integration/test_vector_hybrid_smoke.py`
- `tests/integration/test_smoke_matrix.py`
- `tests/integration/test_ops_commands_smoke.py`

Additional feature tracks are implemented and have unit/CLI coverage, but do not yet all have
their own dedicated Docker-backed end-to-end tests:

- performance analysis
- root-cause analysis
- recommendations
- LTR analysis

## Roadmap snapshot

Available now:

- compatibility detection and fallback reporting
- secure execution and privacy-safe artifact controls
- policy gates with approvals/exceptions metadata
- rollout planning and post-cutover verification
- API service mode and deployment assets

Next:

- richer plugin SDK extension packs for policy and compatibility detectors
- expanded API service multi-user controls and auth/RBAC middleware
- broader enterprise reference dashboards and CI templates

Future direction:

- OIDC/SSO integrations
- live drift monitoring service mode
- vector/hybrid and LTR governance expansion

Roadmap docs:

- `docs/roadmap_api_server.md`
- `docs/enterprise/backlog_next_issues.md`

## Contributing

Contributions are welcome from Solr operators, relevance engineers, and platform teams.

Good first contribution areas:

- add compatibility fixtures for Solr distributions
- add policy bundle examples and test fixtures
- add observability dashboards and webhook adapters
- improve docs and runnable enterprise examples
- harden deployment and CI templates

Developer setup and contribution workflow:

- install: `pip install -e ".[dev]"`
- run tests: `pytest -q -m "not integration"`
- lint: `ruff check .`
- open a PR with artifact or fixture updates when behavior changes

## Troubleshooting

- Configset clone/create returns `401`:
  - set `shadow.allow_shared_configset_fallback: true` for clone-only path.
  - for synonym/stopwords patch ops, use isolated upload path (default) and ensure API permissions.
- Custom configset collection creation fails in Docker SolrCloud with `_version_`-style errors:
  - keep `shadow.promote_uploaded_configset_trusted: true` (default) so uploaded configsets are
    promoted to a trusted configset before shadow create.
- No rewrite diffs shown:
  - verify `evaluation.rewrite_diff.enabled: true`.
  - verify `max_queries` > 0.
  - use `debug_mode: results` if your Solr setup suppresses `debugQuery=true` fields.
- Query replay errors (`400`):
  - logs may contain unsupported params/fields in the target collection.
- `solrguard serve` fails with FastAPI import errors:
  - install current dependencies again with `pip install -e ".[dev]"` so the dashboard extras are present.

## Safety notes

- Tooling is non-AI and deterministic for all scoring/diff metrics.
- Vector lexical-vs-vector contribution values are explicitly heuristic estimates unless
  decomposed Solr score components are available.
- Cleanup is configurable; with cleanup disabled, shadow artifacts remain for manual inspection.
- Reproducibility depends on stable input snapshots and representative docs/queries.
