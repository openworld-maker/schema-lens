# schema-lens

`schema-lens` is a Solr schema/config impact simulator.

It runs a change plan against a shadow collection, replays baseline vs shadow queries, computes
ranking/facet/filter/sort deltas, captures optional explain + rewrite debug diffs, and emits
reproducible JSON/HTML artifacts for human review and CI gates.

Current version: `v0.1.3`

## Table of contents

- [Why it exists](#why-it-exists)
- [Core capabilities](#core-capabilities)
- [Advanced features](#advanced-features)
- [End-to-end flow](#end-to-end-flow)
- [Requirements](#requirements)
- [Quickstart (basic)](#quickstart-basic)
- [Quickstart (synonym rewrite impact)](#quickstart-synonym-rewrite-impact)
- [CLI reference](#cli-reference)
- [Changeset reference](#changeset-reference)
- [Output artifacts](#output-artifacts)
- [Quality gate and CI usage](#quality-gate-and-ci-usage)
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

## CLI reference

### Primary commands

- `schema-lens validate <changeset.yaml>`
- `schema-lens inspect --solr-url URL --collection NAME --out PATH`
- `schema-lens snapshot --solr-url URL --collection NAME --out DIR`
- `schema-lens run <changeset.yaml> --out DIR [--snapshot DIR] [--k K] [--cleanup/--no-cleanup]`
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

## Changeset reference

See [docs/changeset-spec.md](docs/changeset-spec.md).

Notable v0.1.3 additions:

- `schema.synonym.update`
- `schema.stopwords.update`
- `evaluation.rewrite_diff`
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
- `compare.json`
- `report.json`
- `report.html`

`compare.json` and reports include rewrite impact payload when enabled.

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

## Safety notes

- Tooling is non-AI and deterministic for all scoring/diff metrics.
- Cleanup is configurable; with cleanup disabled, shadow artifacts remain for manual inspection.
- Reproducibility depends on stable input snapshots and representative docs/queries.
