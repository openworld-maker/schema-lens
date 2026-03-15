# Schema-Lens Architecture

## Overview

`schema-lens` is a local-first Solr impact simulator. The CLI orchestrates a staged workflow that:

1. captures reproducible baseline metadata
2. provisions a shadow collection/configset
3. loads or samples documents
4. loads or extracts queries
5. replays baseline vs shadow
6. computes ranking and non-ranking diffs
7. emits machine-readable artifacts and a single-file HTML report

The design is additive. New feature tracks attach extra artifacts and report sections without
changing the base replay/compare contract.

## Core Pipeline

```text
changeset + docs + queries
        |
        v
validate -> snapshot -> inspect -> preflight
        |
        v
shadow create -> docs sample/load -> index
        |
        v
queries extract/load -> replay -> compare
        |
        +--> rewrite diff
        +--> explain capture
        +--> vector/hybrid scenario replay
        +--> performance capture
        +--> root-cause analysis
        +--> recommendations
        +--> LTR impact
        |
        v
report.json + report.html + run_manifest.json
```

## Main Packages

### CLI and orchestration

- `schema_lens/cli.py`
- `schema_lens/config.py`
- `schema_lens/errors.py`

`cli.py` owns stage ordering, artifact paths, and run manifest updates. Feature packages expose
small assembler functions so orchestration stays thin.

### Solr transport and APIs

- `schema_lens/http/`
- `schema_lens/solr/`
- `schema_lens/shadow/`

These modules isolate Solr HTTP concerns, retries, admin endpoints, schema APIs, configset
handling, and collection lifecycle management.

### Inputs

- `schema_lens/changesets/`
- `schema_lens/data/`
- `schema_lens/queries/`
- `schema_lens/schema/`
- `schema_lens/snapshot/`

These packages parse/validate changesets, sample documents, extract queries from files/logs,
build schema dependency graphs, and capture deterministic baseline snapshots.

### Replay and compare

- `schema_lens/replay/`
- `schema_lens/compare/`
- `schema_lens/vector/`

`replay` executes lexical baseline/shadow requests. `vector` adds scenario-based replay and
client-side hybrid simulation. `compare` computes ranking, facet, filter, sort, rewrite, explain,
gate, and report-ready summaries.

### Analysis tracks

- `schema_lens/perf/`
- `schema_lens/rootcause/`
- `schema_lens/recommend/`
- `schema_lens/ltr/`
- `schema_lens/env_compare/`
- `schema_lens/monitor/`

These packages are optional, additive tracks:

- `perf`: latency, cache, and index-footprint estimation
- `rootcause`: deterministic diagnosis rules
- `recommend`: action-oriented follow-ups from root causes
- `ltr`: feature-log aware rerank drift
- `env_compare`: cross-cluster drift
- `monitor`: snapshot-vs-current drift history

### Presentation

- `schema_lens/report/`
- `schema_lens/dashboard/`
- `schema_lens/ci/`

`report` builds JSON and HTML bundles. `dashboard` serves a read-only local UI over artifacts on
disk. `ci` formats PR-friendly markdown summaries.

## Artifact Model

Core run artifacts:

- `run_manifest.json`
- `snapshot*.json`
- `schema_risk.json`
- `shadow.json`
- `replay.json`
- `compare.json`
- `report.json`
- `report.html`

Optional additive artifacts:

- `docs_sample.jsonl`
- `queries_extracted.jsonl`
- `vector_validation.json`
- `hybrid_sensitivity.json`
- `perf_metrics.json`
- `rootcauses.json`
- `recommendations.json`
- `env_compare.json`
- `ltr_impact.json`
- `latest_monitor.json`
- `monitor_history.jsonl`

Missing optional capabilities must serialize as:

```json
{"enabled": false, "reason": "..."}
```

This keeps downstream report/dashboard code stable.

## Backward-Compatibility Rules

1. Existing commands stay valid.
2. Existing artifact keys are never removed in-place.
3. New sections are additive only.
4. Feature packages must tolerate partial artifacts and missing Solr capabilities.
5. Deterministic logic is preferred over opaque inference.

## Testing Strategy

1. Fast unit tests cover:
   - parser/validator logic
   - diff metrics
   - root-cause and recommendation rules
   - performance summarization
   - env compare/auth helpers
   - monitor history and drift math
   - LTR feature parsing
2. Docker integration tests cover Solr-dependent behavior.
3. Smoke targets (`make smoke`, `make smoke-vector`, `make smoke-matrix`) validate end-to-end
   slices against the bundled SolrCloud example.
