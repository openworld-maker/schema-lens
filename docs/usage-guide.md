# Schema-Lens Usage Guide

`schema-lens` is a local-first Solr change simulator. It helps you answer one question before you
ship a schema or query-default change:

"What will this change do to ranking, parser behavior, facets, latency, and rollout risk?"

This guide is the operator-focused version of the README. It is organized around what you want to
do, not around internal package layout.

## Start Here

If you are new to the tool, use this order:

1. Run the basic smoke path.
2. Open `report.html`.
3. Inspect `compare.json`.
4. Add only the extra tracks you need: rewrite, vector, performance, env compare, monitor.

Fastest first run:

```bash
make dev-up
make demo-setup
.venv/bin/schema-lens run examples/changesets/fieldtype-change.yaml --out out/demo
open out/demo/report.html
```

## What The Tool Does

At a high level, `schema-lens`:

1. captures baseline collection metadata
2. creates a shadow collection
3. applies your planned schema/config/query-default change
4. indexes representative documents into shadow
5. replays representative queries against baseline and shadow
6. computes diffs and optional analysis tracks
7. emits reproducible JSON and HTML artifacts

Core outputs:

- `report.html`: easiest human review artifact
- `report.json`: structured report bundle for dashboards or automation
- `compare.json`: ranking/facet/filter/sort comparison payload
- `run_manifest.json`: exact input/settings manifest for reproducibility

## Pick The Right Workflow

Use this table as the shortest path to the right command.

| Goal | Command | Primary output |
| --- | --- | --- |
| Validate a changeset before running | `schema-lens validate <changeset>` | terminal validation result |
| Inspect a live collection | `schema-lens inspect --solr-url ... --collection ... --out inspect.json` | `inspect.json` |
| Capture a reproducible baseline snapshot | `schema-lens snapshot --solr-url ... --collection ... --out out/snapshot` | `snapshot.json` bundle |
| Run full baseline vs shadow evaluation | `schema-lens run <changeset> --out out/run` | `report.html`, `report.json`, `compare.json` |
| Replay only, without full run orchestration | `schema-lens replay ... --out replay.json` | `replay.json` |
| Compare an existing replay payload | `schema-lens compare --replay replay.json --out compare.json` | `compare.json` |
| Generate reports from existing compare data | `schema-lens report --compare compare.json --manifest run_manifest.json --out out/report` | `report.json`, `report.html` |
| Apply rollout policy thresholds | `schema-lens gate --compare compare.json --policy policy.yaml` | exit code + terminal summary |
| Produce CI markdown summary | `schema-lens ci summarize --compare compare.json --out summary.md` | `summary.md` |
| Compare two live environments | `schema-lens compare-env --env1 ... --env2 ... --queries ... --out out/env_compare` | `env_compare.json`, `report.html` |
| Generate recommendations from an existing run | `schema-lens recommend --run out/run --out recommendations.json` | `recommendations.json` |
| Serve a read-only artifact dashboard | `schema-lens serve --run out/run --port 8080` | local dashboard |
| Append drift history from a baseline run/snapshot | `schema-lens monitor --baseline-snapshot out/run --queries ... --out out/monitor` | `latest_monitor.json`, `monitor_history.jsonl` |

## Capabilities

### 1. Core ranking diff workflow

This is the default reason to use the tool.

It measures:

- top-K overlap
- Jaccard
- Kendall tau
- moved, dropped, and newly introduced documents
- `numFound` deltas
- facet-count deltas
- sort instability

Use it when:

- changing a field type
- changing analyzers
- changing query defaults
- validating a patch before rollout

### 2. Configset patch simulation

This supports:

- `schema.synonym.update`
- `schema.stopwords.update`

Use it when:

- you want to patch `synonyms.txt` or `stopwords.txt`
- you want a realistic shadow configset instead of only in-memory parameter changes

Best example:

- `examples/changesets/procurement-synonym-rewrite.yaml`

### 3. Rewrite impact analysis

This captures parser behavior changes such as:

- clause explosions
- added/removed terms
- synonym expansion changes
- parsed query shape drift

Use it when:

- synonym changes are risky
- `mm`, `qf`, or parser defaults changed
- you need evidence beyond ranking movement alone

Best example:

- `examples/changesets/procurement-synonym-rewrite.yaml`

Key output:

- `compare.json` -> `rewrite_diff`

### 4. Vector and hybrid simulation

This adds:

- lexical-only scenarios
- vector-only scenarios
- hybrid scenarios
- vector schema validation
- hybrid contribution estimates
- weight sensitivity sweeps

Use it when:

- evaluating a new embedding field
- testing hybrid lexical/vector blends
- comparing sensitivity to hybrid weights

Best example:

- `examples/changesets/vector-hybrid-demo.yaml`

Key outputs:

- `vector_validation.json`
- `replay_<scenario>.json`
- `compare.json` -> `vector_hybrid`
- `hybrid_sensitivity.json`

### 5. Performance and cost impact

This estimates:

- latency regressions
- `QTime` regressions
- cache churn
- index size effects

Use it when:

- a change may alter latency or cache behavior
- you want policy gates on performance, not only relevance

Best example:

- `examples/changesets/perf_estimator_example.yaml`
- `examples/policy/perf_gate_default.yaml`

Key output:

- `perf_metrics.json`

### 6. Root-cause analysis and recommendations

This layer converts comparison evidence into deterministic findings and next steps.

Examples:

- prefix matching removed
- title boost reduced
- minimum-should-match became stricter
- vector dominance increased
- cache or latency regression

Use it when:

- you want faster triage after a failing run
- you want actionable hints for the next iteration

Key outputs:

- `rootcauses.json`
- `recommendations.json`

### 7. Environment compare

This compares two live Solr environments without creating a shadow collection.

Use it when:

- staging and production are drifting
- two regions behave differently
- you need live-vs-live comparison rather than planned change simulation

Best example:

```bash
.venv/bin/schema-lens compare-env \
  --env1 examples/envs/prod_us.yaml \
  --env2 examples/envs/prod_eu.yaml \
  --queries examples/queries/env_compare_queries.jsonl \
  --out out/env_compare
```

Key outputs:

- `env_compare.json`
- `report.html`

### 8. Dashboard and monitoring

`serve` lets you inspect prior artifacts in a lightweight local dashboard.

`monitor` lets you append drift summaries over time:

- `latest_monitor.json`
- `monitor_history.jsonl`

Use these when:

- you want read-only artifact browsing
- you want to track drift after a baseline run

## Easiest Common Workflows

### Basic schema-change workflow

```bash
make dev-up
make demo-setup
.venv/bin/schema-lens run examples/changesets/fieldtype-change.yaml --out out/demo
open out/demo/report.html
```

### Synonym rewrite workflow

```bash
make dev-up
make demo-setup-procurement
.venv/bin/schema-lens run examples/changesets/procurement-synonym-rewrite.yaml --out out/procurement_demo
open out/procurement_demo/report.html
```

### Vector workflow

```bash
make dev-up
make demo-setup-vector
.venv/bin/schema-lens run examples/changesets/vector-hybrid-demo.yaml --out out/vector_demo --enable-sensitivity
open out/vector_demo/report.html
```

### Performance-gated workflow

```bash
make dev-up
make demo-setup
.venv/bin/schema-lens run examples/changesets/perf_estimator_example.yaml --out out/perf_demo
.venv/bin/schema-lens gate --compare out/perf_demo/compare.json --policy examples/policy/perf_gate_default.yaml
```

### Environment drift workflow

```bash
.venv/bin/schema-lens compare-env \
  --env1 examples/envs/prod_us.yaml \
  --env2 examples/envs/prod_eu.yaml \
  --queries examples/queries/env_compare_queries.jsonl \
  --out out/env_compare
open out/env_compare/report.html
```

## How To Read The Results

Open these in order:

1. `report.html`
2. `report.json`
3. `compare.json`

What to look for:

- `summary`: overall overlap and high-risk rate
- `top_regressions`: fastest way to find damaging queries
- `rewrite_diff`: parser-level behavior change
- `vector_hybrid`: lexical vs vector scenario comparison
- `hybrid_sensitivity`: how fragile the chosen weights are
- `performance`: latency/cache/index impact
- `root_causes`: deterministic diagnosis
- `recommendations`: suggested next changes

## How To Choose Inputs

For documents:

- use `data.docs_source.type=file` for reproducible local tests
- use `data.docs_source.type=solr` when you need a realistic sample from a live collection

For queries:

- use `queries.source.type=file` for controlled benchmarks
- use `queries.source.type=log` for production realism

General rule:

- if you are debugging behavior, keep inputs small and reproducible
- if you are deciding rollout risk, use realistic docs and realistic queries

## What Is End-To-End Tested Today

Dedicated Docker-backed integration coverage currently exists for:

- base `run` smoke path
- rewrite-diff smoke path
- vector/hybrid smoke path
- smoke-matrix target

Files:

- `tests/integration/test_run_smoke.py`
- `tests/integration/test_rewrite_diff_smoke.py`
- `tests/integration/test_vector_hybrid_smoke.py`
- `tests/integration/test_smoke_matrix.py`

This means the core workflows are exercised end-to-end.

Not every newer feature has its own dedicated end-to-end smoke yet. The following are implemented,
documented, and unit-tested, but should be treated as not yet fully end-to-end covered by a
feature-specific Docker smoke:

- `compare-env`
- `serve`
- `monitor`
- performance analysis
- root-cause analysis
- recommendations
- LTR analysis

That is good enough for continued development, but not the same as saying every feature has full
integration coverage.

## Recommended Operating Pattern

For production-like use, this is the safest order:

1. `validate`
2. `snapshot`
3. `run`
4. inspect `report.html`
5. apply `gate`
6. optionally use `recommend`, `serve`, `compare-env`, or `monitor`

## Related Docs

- [README.md](../README.md)
- [docs/changeset-spec.md](./changeset-spec.md)
- [docs/architecture.md](./architecture.md)
