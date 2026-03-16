# Contributing to SolrGuard

Thanks for contributing to SolrGuard.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Local quality checks

```bash
ruff check .
pytest -q -m "not integration"
```

Optional integration smoke:

```bash
RUN_SCHEMA_LENS_SMOKE=1 .venv/bin/pytest -q -m integration
```

## Contribution guidelines

- Keep behavior deterministic and artifact-driven.
- Prefer additive, backward-compatible changes where practical.
- Add tests for new behavior and edge cases.
- Update docs/examples for any user-facing change.
- Avoid logging or persisting sensitive values.

## Good first contribution areas

- Compatibility fixtures for Solr versions/distributions.
- Policy bundle examples and governance docs.
- Observability exporters and dashboard examples.
- Privacy-safe artifact fixtures and retention behavior tests.
- Docs clarity and example discoverability improvements.

## Pull request checklist

- [ ] Tests added or updated.
- [ ] Docs/README/examples updated.
- [ ] No sensitive data in fixtures/artifacts.
- [ ] Backward-compatibility impact documented.

## Community behavior

Be respectful and constructive. SolrGuard is built for shared operational safety and transparency.
