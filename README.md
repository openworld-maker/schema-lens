# schema-lens

`schema-lens` is a Solr schema/query impact simulator.
It creates a shadow collection, applies planned changes, replays baseline vs shadow queries, computes relevance diffs, and emits reproducible JSON + HTML reports.

Current version: `v0.1.1`

## Table of contents

- [What problem it solves](#what-problem-it-solves)
- [Key capabilities](#key-capabilities)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quickstart (local SolrCloud)](#quickstart-local-solrcloud)
- [CLI reference](#cli-reference)
- [Output artifacts](#output-artifacts)
- [Changeset guide](#changeset-guide)
- [Production realism workflows](#production-realism-workflows)
- [Quality gate in CI](#quality-gate-in-ci)
- [Testing and validation](#testing-and-validation)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Security and safety notes](#security-and-safety-notes)

## What problem it solves

Solr schema and query-default changes can silently degrade ranking.

`schema-lens` gives a repeatable pre-merge test loop:

1. Build a shadow collection from a baseline collection.
2. Apply schema/query changes from a changeset.
3. Index representative docs.
4. Replay representative queries.
5. Compute per-query impact metrics and risk flags.
6. Produce artifacts suitable for review and CI gating.

## Key capabilities

- SolrCloud-first shadow provisioning via Collections API.
- Schema operation support:
  - `schema.field.update`
  - `schema.fieldType.replace`
  - `schema.analyzer.remove_filter`
  - `queryparams.set`
- Query comparison metrics:
  - Overlap@K
  - Jaccard@K
  - Kendall Tau@K
- Preflight schema safety analysis:
  - field/dynamicField impact
  - copyField dependency risk findings
  - `schema_risk.json` output
- Query sourcing:
  - file (`simple`/`jsonl`)
  - log extraction (`solr_params`/`jsonl`) with sanitization and sampling
- Doc sourcing:
  - local file (`jsonl`/`json`)
  - Solr sampling via `/export` with cursorMark fallback
- Explain capture:
  - classic debug explain
  - structured explain (`debug.explain.structured=true`)
- CI quality gate policies with non-zero exit on failure.
- Reproducible run bundle with manifests and intermediate artifacts.

## How it works

```text
changeset.yaml + docs/query sources
          |
          v
validate -> inspect baseline
          |
          v
schema preflight risk analysis
          |
          v
create shadow collection + apply schema ops
          |
          v
ingest docs (file or sampled from Solr)
          |
          v
ingest queries (file or extracted from logs)
          |
          v
replay baseline vs shadow
          |
          v
compare + risk scoring + optional explains
          |
          v
report.json + report.html (+ all stage artifacts)
```

## Requirements

- Python `3.11+`
- Solr endpoint reachable over HTTP
- For local smoke/integration:
  - Docker + Docker Compose
- Dependencies are installed via:
  - `pip install -e ".[dev]"`

## Quickstart (local SolrCloud)

1. Start local SolrCloud.

```bash
make dev-up
```

2. Create baseline collection and index example docs.

```bash
make demo-setup
```

3. Install and run the end-to-end command.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

schema-lens run examples/changesets/fieldtype-change.yaml --out out/demo
```

4. Review generated outputs.

```bash
cat out/demo/report.json
open out/demo/report.html
```

## CLI reference

### Primary pipeline commands

- `schema-lens validate <changeset.yaml>`
  - Validates changeset structure and required fields.
- `schema-lens inspect --solr-url URL --collection NAME --out PATH`
  - Captures schema/system/cluster snapshot.
- `schema-lens run <changeset.yaml> --out DIR [--k K] [--cleanup/--no-cleanup]`
  - Full orchestration command.
- `schema-lens replay ...`
  - Runs baseline vs shadow query replay from explicit inputs.
- `schema-lens compare --replay PATH --k K --out PATH`
  - Computes diffs and metrics.
- `schema-lens report --compare PATH --manifest PATH --out DIR`
  - Renders `report.json` + `report.html`.

### Shadow lifecycle commands

- `schema-lens shadow create <changeset.yaml> --out shadow.json`
- `schema-lens shadow index --shadow shadow.json --docs docs.jsonl`

### Production realism commands

- `schema-lens queries extract --from <logfile> --out <queries.jsonl> [--max N] [--sample top|reservoir] [--seed INT] [--sanitize/--no-sanitize] [--format solr_params|jsonl]`
- `schema-lens docs sample --solr-url URL --collection NAME --mode export|cursormark --query "*:*" --fl "*" --sort "id asc" --sample-n N --batch-size N --out PATH`
- `schema-lens gate --compare compare.json --policy policy.yaml`
  - Exit code `0` pass
  - Exit code `2` gate fail
  - Exit code `1` runtime/config error

## Output artifacts

A full `run` writes a reproducible bundle under `--out`:

- `run_manifest.json`
- `inspect.json`
- `schema_risk.json`
- `shadow.json`
- `docs_sample.jsonl` (when Solr doc sampling is enabled)
- `queries_extracted.jsonl` (when log query extraction is enabled)
- `replay.json`
- `compare.json`
- `report.json`
- `report.html`

## Changeset guide

Use the canonical spec:

- `docs/changeset-spec.md`

Important v0.1.1 options:

- `preflight.fail_on_risk`
- `data.docs_source.type = file | solr`
- `queries.source.type = file | log`
- `queries.sampling.mode = top | reservoir`
- `queries.sanitize.rules` for PII/token stripping
- `evaluation.explain.structured`

Supported operations:

- `schema.field.update`
- `schema.fieldType.replace`
- `schema.analyzer.remove_filter`
- `queryparams.set`

## Production realism workflows

### Full production-like simulation

```bash
schema-lens run examples/changesets/prod_realism_example.yaml --out out/prod_like_run
```

### Extract canonical replay queries from logs

```bash
schema-lens queries extract \
  --from examples/logs/solr_requests.log \
  --out out/queries_extracted.jsonl \
  --max 500 \
  --sample reservoir \
  --sanitize
```

### Sample realistic docs directly from Solr

```bash
schema-lens docs sample \
  --solr-url http://localhost:8983/solr \
  --collection products \
  --mode cursormark \
  --query "*:*" \
  --fl "id,title,text,category,price" \
  --sort "id asc" \
  --sample-n 5000 \
  --out out/docs_sample.jsonl
```

## Quality gate in CI

Run against a policy:

```bash
schema-lens gate \
  --compare out/prod_like_run/compare.json \
  --policy examples/policy/gate_default.yaml
```

Typical CI usage:

1. Run `schema-lens run ...`
2. Run `schema-lens gate ...`
3. Fail pipeline on exit code `2`

Included policy examples:

- `examples/policy/gate_default.yaml`
- `examples/queries/golden.jsonl`

## Testing and validation

### Fast local checks

```bash
ruff check .
pytest -q -m "not integration"
```

### Local smoke test

```bash
make smoke
```

### Scenario matrix (basic + complex paths)

```bash
make smoke-matrix
```

### Integration-marked tests

```bash
RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration
```

### GitHub Actions

- CI workflow runs lint + unit tests on push/PR.
- `Smoke Matrix` workflow can be triggered manually in GitHub Actions.

## Project structure

```text
schema_lens/
  cli.py
  changesets/
  compare/
  data/
  http/
  queries/
  replay/
  report/
  schema/
  shadow/
  solr/
tests/
examples/
docs/
```

## Troubleshooting

- Configset clone returns `401` in SolrCloud:
  - Set `shadow.allow_shared_configset_fallback: true` for non-isolated fallback mode.
- Query replay returns Solr `400`:
  - Logs may contain fields/sorts not present in sampled schema/docs.
  - Filter/sort parameters are preserved by design for realism.
- Low overlap in sample data:
  - Verify `docs_source` and `queries_source` represent the same domain/time period.
- Missing expected artifacts:
  - Confirm `--out` directory and stage statuses in `run_manifest.json`.

## Security and safety notes

- Keep sanitization enabled for log-based query ingestion in non-local environments.
- Minimize sampled field list (`fl`) to required fields.
- Treat `schema_risk.json` HIGH findings as rollout blockers.
- Use `gate` with policy thresholds to enforce change control in CI.
