# schema-lens

Schema Lens is a Solr schema evolution impact simulator. It compares baseline vs shadow relevance before you ship schema/query changes.

Target first release: `v0.1.0`.

## Why

Schema and query parameter changes can silently degrade ranking quality. `schema-lens` runs an offline replay against a shadow collection so you can inspect overlap/rank changes and debug regressions.

## Features (v0.1)

- CLI commands: `validate`, `inspect`, `shadow create`, `shadow index`, `replay`, `compare`, `report`, `run`
- SolrCloud-first shadow collection lifecycle via Collections API
- Schema change operations:
  - `schema.field.update`
  - `schema.fieldType.replace`
  - `schema.analyzer.remove_filter`
  - `queryparams.set`
- Query replay and metrics: overlap@K, jaccard@K, kendall tau@K
- Reproducible outputs: `run_manifest.json`, `replay.json`, `compare.json`, `report.json`, `report.html`

## Quickstart

### 1) Start local SolrCloud

```bash
make dev-up
```

### 2) Create baseline collection and index sample docs

```bash
make demo-setup
```

### 3) Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

schema-lens run examples/changesets/fieldtype-change.yaml --out out/demo
```

### 4) Inspect report

```bash
cat out/demo/report.json
```

## Example command

```bash
schema-lens run examples/changesets/fieldtype-change.yaml \
  --out out/run_2026-02-28T2200 \
  --k 10 \
  --cleanup
```

## Sample report section

```json
{
  "summary": {
    "queries_total": 5,
    "failures": 0,
    "avg_overlap": 8.4,
    "high_risk_percent": 20.0
  }
}
```

## How it works

```text
changeset.yaml + docs + queries
          |
          v
    validate inputs
          |
          v
 inspect baseline schema/system
          |
          v
  create shadow collection
          |
          v
 apply schema changes to shadow
          |
          v
   index docs into shadow
          |
          v
replay queries baseline vs shadow
          |
          v
compute diffs + metrics + explains
          |
          v
 generate report.json + report.html
```

## Changeset format

See [docs/changeset-spec.md](docs/changeset-spec.md).

## Development

```bash
ruff check .
pytest -q -m "not integration"
```

Smoke test:

```bash
make smoke
```

Comprehensive local scenario matrix:

```bash
make smoke-matrix
```

Manual GitHub Actions matrix run:
`Actions` -> `Smoke Matrix` -> `Run workflow`.
