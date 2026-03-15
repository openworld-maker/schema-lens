# Plugin SDK

`schema-lens` includes an optional Plugin SDK for enterprise extension points.

## Goals

- Keep core CLI contracts stable.
- Allow custom integrations without forking `schema-lens`.
- Keep failures isolated unless strict mode is enabled.

## Lifecycle

Each plugin can implement four hooks:

1. `validate(context)`
2. `initialize(context)`
3. `execute(context, payload)`
4. `cleanup(context)`

Lifecycle guarantees:

- Exceptions are recorded in `plugins.json` and `report.json`.
- Run aborts only when `plugins.strict: true`.
- `cleanup()` is always attempted for initialized plugins.

## Extension Points

Contracts are available in `schema_lens/plugins/contracts/`:

- `auth.py` (`AuthProviderPlugin`)
- `query_source.py` (`QuerySourcePlugin`)
- `doc_source.py` (`DocSourcePlugin`)
- `replay.py` (`ReplayExecutorPlugin`)
- `analyzer.py` (`DiffAnalyzerPlugin`, `RootCauseRulePlugin`, `RecommendationRulePlugin`)
- `gate.py` (`GateEvaluatorPlugin`)
- `report.py` (`ReportRendererPlugin`, `ReportWidgetPlugin`)
- `observability.py` (`ObservabilityExporterPlugin`)
- `rollout.py` (`RolloutProviderPlugin`)

## Config

Set plugin runtime config in your changeset:

```yaml
plugins:
  enabled: true
  strict: false
  entry_points: true
  entry_point_group: schema_lens.plugins
  paths:
    - ./examples/plugins/sample_query_source
    - ./examples/plugins/sample_gate
  enable_plugins:
    - sample_query_source
    - sample_gate
  disable_plugins: []
```

Or reference a dedicated YAML file:

```yaml
plugins:
  config: ./examples/plugins/plugins_runtime.yaml
```

## Metadata and Versioning

Each plugin must define `metadata`:

- `name`
- `version`
- `plugin_type`
- `capabilities`
- `schema_lens_version` range (for compatibility checks)

Compatibility policy:

- Plugin runtime checks `schema_lens_version` before activation.
- Incompatible plugins are recorded as issues and skipped.
- Strict mode turns compatibility issues into run-blocking errors.

## Discovery

Plugin loading supports:

- Python entry points (`schema_lens.plugins` by default)
- Local plugin directories/files via `plugins.paths`
- Explicit enable/disable lists (`enable_plugins`, `disable_plugins`)

Supported module patterns for local plugins:

- `register_plugins(registry)` function
- `PLUGINS = [PluginClass, ...]`
- `PLUGIN = PluginClass`

## Artifacts

Plugin outputs are written to:

- `plugins.json`
- `compare.json.plugins`
- `report.json.plugins`

Issues include stage and message for quick triage.

## Examples

See:

- `examples/plugins/sample_query_source/`
- `examples/plugins/sample_gate/`
- `examples/plugins/sample_report_widget/`

