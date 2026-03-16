# Plugin SDK

`solrguard` includes a first-class Plugin SDK so enterprise and community teams can extend behavior without forking core code.

## 1) Architecture Overview

Core plugin framework files live in `schema_lens/plugins/`:

- `base.py`: plugin metadata, context, lifecycle base class
- `registry.py`: plugin registration and lookup
- `loader.py`: built-in, local directory, and entry-point discovery
- `manifest.py`: plugin run-manifest/artifact models
- `hooks.py`: lifecycle phase names
- `errors.py`: structured plugin issues/errors

Runtime orchestration is in `schema_lens/runtime/plugin_service.py`.

## 2) Supported Plugin Types

Contracts are under `schema_lens/plugins/contracts/`:

- `AuthProviderPlugin`
- `QuerySourcePlugin`
- `DocSourcePlugin`
- `ReplayExecutorPlugin`
- `DiffAnalyzerPlugin`
- `RootCauseRulePlugin`
- `RecommendationRulePlugin`
- `GateEvaluatorPlugin`
- `ReportRendererPlugin` / `ReportWidgetPlugin`
- `ObservabilityExporterPlugin`
- `RolloutProviderPlugin`

## 3) Metadata Requirements

Each plugin must define `metadata`:

- `name`
- `version`
- `description`
- `plugin_type`
- `compatible_schema_lens_version`
- `capabilities`

Example:

```python
metadata = PluginMetadata(
    name="sample_query_source",
    version="0.1.0",
    plugin_type="query_source",
    description="Loads custom query JSON rows",
    compatible_schema_lens_version=">=0.1.0",
    capabilities=["query_source:file"],
)
```

`schema_lens_version` remains accepted for backward compatibility.

## 4) Lifecycle Hooks

Plugin lifecycle:

1. `validate_config(config)`
2. `validate(context)`
3. `initialize(context)`
4. type-specific hooks (query/doc/gate/report/observability/etc.)
5. `execute(context, payload)` (generic finalize stage)
6. `cleanup(context)`

Errors are isolated and recorded in plugin artifacts and `plugins.json`. With `strict_mode: true`, plugin failures block the run.

## 5) Build Examples

### Query Source Plugin

Implement `validate_source(config)` and `load_queries(config, context)`:

- Config path from `plugins.config.<plugin_name>`
- Return list of rows convertible to `QueryCase` (for example `query_text`, `filters`, `tenant`)

Reference: `examples/plugins/sample_query_source/sample_query_source.py`

### Gate Plugin

Implement `evaluate(policy, artifacts) -> dict`:

- Read compare artifacts (for example `compare_data["diffs"]`)
- Return deterministic pass/fail payload

Reference: `examples/plugins/sample_gate/sample_gate.py`

### Report Plugin

Implement:

- `render_json_section(run_context, artifacts) -> dict`
- `render_html_section(run_context, artifacts) -> str`

Reference: `examples/plugins/sample_report/sample_report.py`

## 6) Testing Guidance

Recommended tests:

- metadata validation
- registry registration/lookup
- loader behavior for built-in/local/entry-point plugins
- strict mode behavior
- compatibility filtering
- exception isolation
- plugin config parsing
- artifact path generation
- plugin integration tests for query source, gate, and report output

Current tests:

- `tests/test_plugins.py`
- `tests/integration/test_plugin_sdk_integration.py`

## 7) Version Compatibility Guidance

- Declare `compatible_schema_lens_version` conservatively.
- If runtime version is outside range, plugin is skipped and logged as compatibility issue.
- Use `plugins.strict_mode: true` in CI/production to block incompatible plugins.
- Keep plugin contracts deterministic and avoid mutating core artifacts in-place.

