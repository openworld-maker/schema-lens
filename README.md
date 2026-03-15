# schema-lens

`schema-lens` is a Solr schema/config impact simulator.

It runs a change plan against a shadow collection, replays baseline vs shadow queries, computes
ranking/facet/filter/sort deltas, captures optional explain + rewrite debug diffs, and emits
reproducible JSON/HTML artifacts for human review and CI gates.

Current version: `v0.2.0`

## Table of contents

- [Why it exists](#why-it-exists)
- [Core capabilities](#core-capabilities)
- [Advanced features](#advanced-features)
- [End-to-end flow](#end-to-end-flow)
- [Requirements](#requirements)
- [Quickstart (basic)](#quickstart-basic)
- [Quickstart (synonym rewrite impact)](#quickstart-synonym-rewrite-impact)
- [Quickstart (vector and hybrid simulation)](#quickstart-vector-and-hybrid-simulation)
- [CLI reference](#cli-reference)
- [Changeset reference](#changeset-reference)
- [Output artifacts](#output-artifacts)
- [Quality gate and CI usage](#quality-gate-and-ci-usage)
- [Architecture](#architecture)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Safety notes](#safety-notes)

## Why it exists

Schema/analyzer/query-default changes can silently degrade relevance. Teams need a reproducible
way to answer:

1. What changed in ranking quality?
2. Which queries/documents were impacted?
3. Did parser/rewrite behavior change (synonyms, clause shape, mm pressure)?
4. Should CI block rollout?

`schema-lens` provides this as a local-first CLI workflow.

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

- In SolrCloud environments where uploaded configsets are untrusted, schema-lens can promote the
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

If `debug=results` does not include parsed query fields on your Solr setup, schema-lens
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

Schema-Lens can convert diff evidence into deterministic root-cause findings and action-oriented
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

## Quickstart (basic)

1. Start local SolrCloud:

```bash
make dev-up
```

2. Create baseline `products` collection and index sample docs:

```bash
make demo-setup
```

3. Run schema-lens:

```bash
schema-lens run examples/changesets/fieldtype-change.yaml --out out/demo
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
schema-lens run examples/changesets/procurement-synonym-rewrite.yaml --out out/procurement_demo
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
schema-lens run examples/changesets/vector-hybrid-demo.yaml --out out/vector_demo --enable-sensitivity
```

4. Inspect vector outputs:

```bash
cat out/vector_demo/compare.json | rg "vector_hybrid|hybrid_sensitivity|dominance"
cat out/vector_demo/hybrid_sensitivity.json
open out/vector_demo/report.html
```

## CLI reference

### Primary commands

- `schema-lens validate <changeset.yaml>`
- `schema-lens inspect --solr-url URL --collection NAME --out PATH`
- `schema-lens snapshot --solr-url URL --collection NAME --out DIR`
- `schema-lens run <changeset.yaml> --out DIR [--snapshot DIR] [--k K] [--cleanup/--no-cleanup] [--scenario NAME ...] [--enable-sensitivity/--no-enable-sensitivity] [--weights CSV] [--vector-dimension-override INT]`
- `schema-lens replay --baseline-solr-url ... --baseline-collection ... --shadow-solr-url ... --shadow-collection ... --queries ... --k ... --out ...`
- `schema-lens compare --replay PATH --k K --out PATH`
- `schema-lens report --compare PATH --manifest PATH --out DIR`

### Shadow lifecycle

- `schema-lens shadow create <changeset.yaml> --out shadow.json`
- `schema-lens shadow index --shadow shadow.json --docs docs.jsonl`

### Query/doc source tooling

- `schema-lens queries extract --from <logfile> --out <queries.jsonl> [--max N] [--sample top|reservoir] [--seed INT] [--sanitize/--no-sanitize]`
- `schema-lens docs sample --solr-url URL --collection NAME --mode export|cursormark --query "*:*" --fl "*" --sort "id asc" --sample-n N --batch-size N --out PATH`

### Golden + CI helpers

- `schema-lens golden add --q "..." --expect-id DOC123 --out golden.jsonl`
- `schema-lens golden discover --from queries.jsonl --top 50 --out golden.jsonl`
- `schema-lens gate --compare compare.json --policy policy.yaml`
- `schema-lens ci summarize --compare compare.json --out summary.md [--policy policy.yaml]`

### Analysis and operations helpers

- `schema-lens recommend --run out/run_xxx --out out/recommendations.json`
- `schema-lens compare-env --env1 examples/envs/prod_us.yaml --env2 examples/envs/prod_eu.yaml --queries examples/queries/env_compare_queries.jsonl --out out/env_compare`
- `schema-lens serve --run out/demo --port 8080`
- `schema-lens serve --compare out/env_compare/compare.json --port 8080`
- `schema-lens monitor --baseline-snapshot out/demo --queries examples/queries/env_compare_queries.jsonl --out out/monitor`

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
- `rootcauses.json`
- `recommendations.json`
- `env_compare.json` (for `compare-env`)
- `ltr_impact.json`
- `latest_monitor.json` / `monitor_history.jsonl` (for `monitor`)
- `report.json`
- `report.html`

`compare.json` and reports include additive sections for rewrite impact, vector/hybrid simulation,
performance, root-cause analysis, recommendations, environment drift, and LTR when available.

## Quality gate and CI usage

Run policy gate:

```bash
schema-lens gate --compare out/demo/compare.json --policy examples/policy/gate_default.yaml
```

Exit codes:

- `0`: pass
- `2`: policy fail
- `1`: runtime/config error

Generate PR-friendly markdown summary:

```bash
schema-lens ci summarize --compare out/demo/compare.json --policy examples/policy/gate_default.yaml --out out/demo/summary.md
```

GitHub Actions workflows included:

- `.github/workflows/ci.yml` (lint + unit + relevance summary job)
- `.github/workflows/smoke-matrix.yml` (manual matrix run)

## Architecture

See [docs/architecture.md](docs/architecture.md) for the package map, stage flow, artifact model,
and extension rules for new tracks.

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
.venv/bin/schema-lens run examples/changesets/perf_estimator_example.yaml --out out/perf_demo
.venv/bin/schema-lens gate --compare out/perf_demo/compare.json --policy examples/policy/perf_gate_default.yaml
```

Environment compare example:

```bash
.venv/bin/schema-lens compare-env \
  --env1 examples/envs/prod_us.yaml \
  --env2 examples/envs/prod_eu.yaml \
  --queries examples/queries/env_compare_queries.jsonl \
  --out out/env_compare
```

Integration-marked tests:

```bash
RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration
```

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
- `schema-lens serve` fails with FastAPI import errors:
  - install current dependencies again with `pip install -e ".[dev]"` so the dashboard extras are present.

## Safety notes

- Tooling is non-AI and deterministic for all scoring/diff metrics.
- Vector lexical-vs-vector contribution values are explicitly heuristic estimates unless
  decomposed Solr score components are available.
- Cleanup is configurable; with cleanup disabled, shadow artifacts remain for manual inspection.
- Reproducibility depends on stable input snapshots and representative docs/queries.
