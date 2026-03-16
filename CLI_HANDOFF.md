# CLI Handoff

## Current Objective

Continue work in `/Users/gaurav/Documents/PersonalProjects/schema-lens` from the current dirty worktree without losing any in-progress feature implementation.

Primary immediate goal:

- preserve current green state
- review final diffs
- make any last docs/cleanup fixes
- commit/push in logical slices or as one validated batch

## Read First

1. `/Users/gaurav/Documents/PersonalProjects/schema-lens/PROJECT_CONTEXT.md`
2. `/Users/gaurav/Documents/PersonalProjects/schema-lens/README.md`
3. `/Users/gaurav/Documents/PersonalProjects/schema-lens/docs/architecture.md`

## Exact Next Command Sequence

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
git status --short
git diff --stat
.venv/bin/ruff check .
.venv/bin/pytest -q -m 'not integration'
make dev-up
/bin/zsh -lc 'RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration'
```

If those stay green, inspect changes:

```bash
git diff -- README.md docs/changeset-spec.md docs/architecture.md
git diff -- schema_lens/cli.py schema_lens/report/json_report.py schema_lens/report/templates/report.html.j2
git diff -- schema_lens/vector/query_builder.py schema_lens/vector/blend.py tests/test_hybrid_blend.py
```

Then decide commit strategy:

```bash
git add -A
git commit -m "Add performance, diagnosis, env compare, dashboard, monitoring, LTR, and vector fixes"
```

Or split into smaller commits if preferred.

## Known Risks / Blockers

1. The repo is not clean.
   - Do not reset or discard unrelated modifications.

2. Docker-backed integration matters.
   - Unit tests alone are not enough for this repo.

3. Some localhost / Solr checks may require running outside the sandbox.
   - If local Python cannot reach `localhost:8983`, rerun integration commands with escalation.

4. `cli.py` and `report.html.j2` are high-conflict files.
   - Re-check them carefully before committing.

5. New feature tracks are additive but broad.
   - Keep report JSON, compare JSON, and manifest fields consistent if you touch them again.

## Most Recent Critical Fixes

1. Vector request builder no longer leaks `defType=edismax` into KNN requests.
2. Hybrid normalized blend no longer zeroes out single-result lexical streams.

These files are especially important:

- `/Users/gaurav/Documents/PersonalProjects/schema-lens/schema_lens/vector/query_builder.py`
- `/Users/gaurav/Documents/PersonalProjects/schema-lens/schema_lens/vector/blend.py`
- `/Users/gaurav/Documents/PersonalProjects/schema-lens/tests/test_hybrid_blend.py`

## If You Need A Quick Smoke Demo

```bash
cd /Users/gaurav/Documents/PersonalProjects/schema-lens
make dev-up
.venv/bin/python scripts/setup_vector_demo.py
.venv/bin/solrguard run examples/changesets/vector-hybrid-demo.yaml --out out/vector_demo --enable-sensitivity
```

Expected artifacts:

- `out/vector_demo/report.json`
- `out/vector_demo/report.html`
- `out/vector_demo/compare.json`
- `out/vector_demo/hybrid_sensitivity.json`
