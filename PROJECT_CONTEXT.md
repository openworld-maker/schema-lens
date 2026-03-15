# Schema-Lens Project Context

This file is a handoff note for continuing work from the Codex CLI without re-discovering repo state.

## Repo

- Path: `/Users/gaurav/Documents/PersonalProjects/schema-lens`
- Current branch at handoff: `ops/use-gemini-runtime-b3e0aba-1772611103`
- Worktree state: dirty, with many staged-equivalent local modifications and new files not yet committed
- Important rule: do not revert unrelated changes; continue from current worktree

## Current Status

The repo already includes substantial implementation beyond the original MVP:

- Core CLI pipeline exists:
  - `validate`
  - `inspect`
  - `shadow create`
  - `shadow index`
  - `replay`
  - `compare`
  - `report`
  - `run`
- Production realism features exist:
  - schema preflight / dependency risk
  - query log extraction
  - Solr doc sampling
  - structured explain support
  - quality gate
- Usability and CI features exist:
  - snapshot support
  - golden queries/docs
  - facet / numFound / sort diffs
  - CI summarize
- Synonym / query rewrite work exists
- Vector / hybrid simulation exists
- New parallel-program track packages were added:
  - `schema_lens/perf/`
  - `schema_lens/rootcause/`
  - `schema_lens/recommend/`
  - `schema_lens/env_compare/`
  - `schema_lens/dashboard/`
  - `schema_lens/monitor/`
  - `schema_lens/ltr/`

## What Was Fixed Most Recently

Two issues were resolved in the vector/hybrid path:

1. KNN requests were incorrectly inheriting lexical parser settings.
   - Fixed in `schema_lens/vector/query_builder.py`
   - `defType=edismax` is no longer passed into vector-only KNN requests
   - JSON request filters are propagated to vector requests as `fq`

2. Hybrid normalized blending collapsed single-doc lexical results to zero contribution.
   - Fixed in `schema_lens/vector/blend.py`
   - zero-variance normalization now returns `1.0` per present doc instead of `0.0`
   - this restored real weight sensitivity and fixed the vector smoke test

Regression coverage for this was added in:

- `tests/test_hybrid_blend.py`

## Validation State At Handoff

These were run successfully from the current worktree:

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
.venv/bin/ruff check .
.venv/bin/pytest -q -m 'not integration'
/bin/zsh -lc 'RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q tests/integration/test_vector_hybrid_smoke.py'
/bin/zsh -lc 'RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration'
```

Result at handoff:

- lint: passing
- unit tests: passing
- Docker integration suite: passing
- vector hybrid smoke: passing

## Docker / Local Runtime

The local SolrCloud demo stack is already wired and was used successfully:

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
make dev-up
docker compose -f examples/solrcloud-docker/docker-compose.yml ps
```

Expected Solr endpoint:

- `http://localhost:8983/solr`

## Important Files Added Or Heavily Updated

### Core / CLI / Reporting

- `schema_lens/cli.py`
- `schema_lens/report/json_report.py`
- `schema_lens/report/templates/report.html.j2`
- `docs/architecture.md`
- `README.md`
- `docs/changeset-spec.md`

### New Packages

- `schema_lens/perf/`
- `schema_lens/rootcause/`
- `schema_lens/recommend/`
- `schema_lens/env_compare/`
- `schema_lens/dashboard/`
- `schema_lens/monitor/`
- `schema_lens/ltr/`
- `schema_lens/vector/`

### Solr API support

- `schema_lens/solr/endpoints.py`
- `schema_lens/solr/admin_api.py`
- `schema_lens/solr/query_api.py`

### Vector demo / examples

- `scripts/setup_vector_demo.py`
- `examples/changesets/vector-hybrid-demo.yaml`
- `examples/queries/procurement_vector_queries.jsonl`
- `examples/vectors/embeddings_small.jsonl`
- `examples/solrcloud-docker/configsets/products_vector/conf/managed-schema.xml`

### Performance / env compare examples

- `examples/changesets/perf_estimator_example.yaml`
- `examples/policy/perf_gate_default.yaml`
- `examples/envs/prod_us.yaml`
- `examples/envs/prod_eu.yaml`
- `examples/queries/procurement_perf_queries.jsonl`
- `examples/queries/env_compare_queries.jsonl`

## Current Worktree Reality

There are many modified and untracked files. Treat the repo as an in-progress feature branch, not a clean baseline.

Representative modified files:

- `Makefile`
- `pyproject.toml`
- `schema_lens/changesets/model.py`
- `schema_lens/changesets/validator.py`
- `schema_lens/ci/summarize.py`
- `schema_lens/compare/diff.py`
- `schema_lens/compare/gate.py`
- `schema_lens/compare/rewrite_diff.py`
- `schema_lens/queries/loader.py`
- `schema_lens/queries/model.py`
- `schema_lens/queries/normalize.py`
- `schema_lens/replay/runner.py`
- `tests/test_changeset_validator.py`
- `tests/test_query_loader.py`

Many new directories are untracked and should likely be committed together as one logical batch after review.

## Suggested Next Steps

If continuing from CLI, the safest sequence is:

1. Inspect diff scope:

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
git status --short
git diff --stat
```

2. Re-run fast validation after any edits:

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q -m 'not integration'
```

3. Re-run Docker integration before commit:

```bash
make dev-up
/bin/zsh -lc 'RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration'
```

4. Review docs for consistency with the actual CLI surface:
   - `README.md`
   - `docs/changeset-spec.md`
   - `docs/architecture.md`

5. Commit in one or more logical slices, but avoid partial commits that leave report/CLI/test contracts inconsistent.

## Recommended Commit Slicing

If you want cleaner history, split into:

1. `contract/report/docs` slice
2. `perf/rootcause/recommend` slice
3. `env_compare/dashboard/monitor/ltr` slice
4. `vector/hybrid fixes + tests` slice

If speed matters more than history quality, one validated commit is acceptable.

## Known Constraints

- Network access may be restricted in the environment
- Some localhost / Docker-backed tests may require running outside the sandbox
- Docker-based Solr validation is important; many features are not meaningfully verified by unit tests alone
- Do not assume the repo is on `main`; it is not at handoff

## High-Value Commands

### Full local validation

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
.venv/bin/ruff check .
.venv/bin/pytest -q -m 'not integration'
make dev-up
/bin/zsh -lc 'RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration'
```

### Representative demos

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
make dev-up
make demo-setup
.venv/bin/schema-lens run examples/changesets/prod_realism_example.yaml --out out/prod_like_run
.venv/bin/python scripts/setup_vector_demo.py
.venv/bin/schema-lens run examples/changesets/vector-hybrid-demo.yaml --out out/vector_demo --enable-sensitivity
```

### Useful outputs

- `out/integration_vector/report.json`
- `out/integration_vector/report.html`
- `out/integration_vector/compare.json`
- `out/integration_vector/hybrid_sensitivity.json`

## Handoff Note

At handoff, the implementation is in a materially better state than the original plan baseline:

- the broad feature surface exists
- tests are green
- Docker integration is green
- the latest vector/hybrid regression was fixed

The main remaining work is likely cleanup, commit structuring, final docs consistency review, and any next feature pack the user chooses.
