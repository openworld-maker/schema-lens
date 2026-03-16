from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schema_lens.errors import StageError
from schema_lens.plugins import (
    HOOKS,
    PluginArtifactPaths,
    PluginContext,
    PluginResult,
    PluginRunManifest,
    load_plugin_runtime_config,
    load_plugins,
    validate_issues,
)
from schema_lens.plugins.base import BasePlugin
from schema_lens.plugins.contracts.observability import ObservabilityExporterPlugin
from schema_lens.plugins.utils import normalize_plugin_payload
from schema_lens.util.io import ensure_dir, read_json, write_json, write_text


@dataclass
class PluginRuntime:
    enabled: bool
    strict: bool
    plugin_configs: dict[str, dict[str, Any]]
    active_plugins: list[BasePlugin] = field(default_factory=list)
    active_by_type: dict[str, list[BasePlugin]] = field(default_factory=dict)
    initialized_plugins: list[BasePlugin] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    manifest: PluginRunManifest = field(default_factory=PluginRunManifest)
    plugins_root: Path | None = None


def plugin_artifact_paths(out_dir: Path, plugin_name: str) -> PluginArtifactPaths:
    root = out_dir / "plugins" / plugin_name
    ensure_dir(root)
    return PluginArtifactPaths(
        root=root,
        result_json=root / "result.json",
        debug_json=root / "debug.json",
        notes_txt=root / "notes.txt",
    )


def _plugin_issue(
    *,
    plugin: BasePlugin,
    stage: str,
    message: str,
    fatal: bool,
) -> dict[str, Any]:
    return {
        "plugin": plugin.metadata.name,
        "plugin_type": plugin.metadata.plugin_type,
        "stage": stage,
        "message": message,
        "fatal": fatal,
    }


def _build_context(
    *,
    runtime: PluginRuntime,
    run_id: str,
    out_dir: Path,
    changeset_path: Path,
    changeset_raw: dict[str, Any],
    manifest_payload: dict[str, Any],
    phase: str,
) -> PluginContext:
    return PluginContext(
        run_id=run_id,
        out_dir=out_dir.resolve(),
        changeset_path=changeset_path.resolve(),
        changeset=changeset_raw,
        manifest=manifest_payload,
        strict=runtime.strict,
        phase=phase,
        plugin_configs=runtime.plugin_configs,
    )


def _write_plugin_artifact(
    *,
    runtime: PluginRuntime,
    out_dir: Path,
    plugin: BasePlugin,
    phase: str,
    payload: dict[str, Any],
    warning: str | None = None,
) -> str:
    paths = plugin_artifact_paths(out_dir.resolve(), plugin.metadata.name)
    normalized_payload = normalize_plugin_payload(payload)
    result_payload = {"plugin": plugin.metadata.name, "phase": phase, "result": normalized_payload}
    write_json(paths.result_json, result_payload)
    debug_payload = read_json(paths.debug_json) if paths.debug_json.exists() else {"stages": []}
    stages = debug_payload.get("stages")
    if not isinstance(stages, list):
        stages = []
    stages.append(result_payload)
    debug_payload["stages"] = stages
    write_json(paths.debug_json, debug_payload)
    if warning:
        existing = paths.notes_txt.read_text(encoding="utf-8") if paths.notes_txt.exists() else ""
        write_text(paths.notes_txt, f"{existing}{warning}\n")

    runtime.manifest.output_artifacts[plugin.metadata.name] = {
        "root": str(paths.root),
        "result_json": str(paths.result_json),
        "debug_json": str(paths.debug_json),
        "notes_txt": str(paths.notes_txt),
    }
    return str(paths.root)


def _handle_plugin_exception(
    *,
    runtime: PluginRuntime,
    out_dir: Path,
    plugin: BasePlugin,
    stage: str,
    exc: Exception,
    logger: logging.Logger,
) -> None:
    issue = _plugin_issue(
        plugin=plugin,
        stage=stage,
        message=str(exc),
        fatal=runtime.strict,
    )
    runtime.issues.append(issue)
    runtime.manifest.failed_plugins.append(issue)
    _write_plugin_artifact(
        runtime=runtime,
        out_dir=out_dir,
        plugin=plugin,
        phase=stage,
        payload=normalize_plugin_payload({"error": str(exc)}),
        warning=f"[{stage}] {exc}",
    )
    if runtime.strict:
        raise StageError(f"plugin {stage} failed ({plugin.metadata.name}): {exc}") from exc
    logger.warning("Plugin %s failed at %s: %s", plugin.metadata.name, stage, exc)


def initialize_plugins(
    *,
    changeset_raw: dict[str, Any],
    changeset_path: Path,
    run_id: str,
    out_dir: Path,
    manifest_payload: dict[str, Any],
    logger: logging.Logger,
) -> PluginRuntime:
    plugin_cfg = load_plugin_runtime_config(changeset_raw, changeset_path)
    loaded_plugins = load_plugins(
        plugin_cfg,
        base_dir=changeset_path.parent.resolve(),
    )
    issues = [issue.to_dict() for issue in loaded_plugins.issues]
    validate_issues(loaded_plugins.issues, strict=plugin_cfg.strict_mode)

    runtime = PluginRuntime(
        enabled=plugin_cfg.enabled,
        strict=plugin_cfg.strict_mode,
        plugin_configs=plugin_cfg.config,
        issues=issues,
        active_by_type={},
        plugins_root=(out_dir / "plugins"),
    )
    ensure_dir(runtime.plugins_root)
    runtime.settings = {
        "enabled": plugin_cfg.enabled,
        "strict_mode": plugin_cfg.strict_mode,
        "load_builtin": plugin_cfg.load_builtin,
        "entry_points": plugin_cfg.enable_entry_points,
        "entry_point_group": plugin_cfg.entry_point_group,
        "directories": plugin_cfg.directories,
        "enabled_plugins": plugin_cfg.enabled_plugins,
        "loaded_plugins": loaded_plugins.registry.list_plugins(),
        "issues": issues,
    }

    context = _build_context(
        runtime=runtime,
        run_id=run_id,
        out_dir=out_dir,
        changeset_path=changeset_path,
        changeset_raw=changeset_raw,
        manifest_payload=manifest_payload,
        phase=HOOKS.initialize,
    )

    for plugin in loaded_plugins.active:
        plugin_config = runtime.plugin_configs.get(plugin.metadata.name, {})
        try:
            plugin.validate_config(plugin_config if isinstance(plugin_config, dict) else {})
            plugin.validate(context)
            plugin.initialize(context)
            runtime.active_plugins.append(plugin)
            runtime.initialized_plugins.append(plugin)
            runtime.manifest.loaded_plugins.append(
                {
                    "name": plugin.metadata.name,
                    "version": plugin.metadata.version,
                    "description": plugin.metadata.description,
                    "plugin_type": plugin.metadata.plugin_type,
                    "capabilities": plugin.metadata.capabilities,
                    "required": bool(plugin.required),
                    "config": plugin.redact(plugin_config if isinstance(plugin_config, dict) else {}),
                }
            )
            _write_plugin_artifact(
                runtime=runtime,
                out_dir=out_dir,
                plugin=plugin,
                phase=HOOKS.initialize,
                payload={"status": "initialized"},
            )
        except Exception as exc:  # noqa: BLE001
            _handle_plugin_exception(
                runtime=runtime,
                out_dir=out_dir,
                plugin=plugin,
                stage=HOOKS.initialize,
                exc=exc,
                logger=logger,
            )

    runtime.active_by_type = {}
    for plugin in runtime.active_plugins:
        runtime.active_by_type.setdefault(plugin.metadata.plugin_type, []).append(plugin)

    return runtime


def get_plugins_by_type(runtime: PluginRuntime | None, plugin_type: str) -> list[BasePlugin]:
    if runtime is None:
        return []
    return runtime.active_by_type.get(plugin_type, [])


def get_plugin_config(runtime: PluginRuntime | None, plugin_name: str) -> dict[str, Any]:
    if runtime is None:
        return {}
    config = runtime.plugin_configs.get(plugin_name, {})
    return config if isinstance(config, dict) else {}


def select_plugin(
    runtime: PluginRuntime | None,
    *,
    plugin_type: str,
    plugin_name: str,
) -> BasePlugin | None:
    for plugin in get_plugins_by_type(runtime, plugin_type):
        if plugin.metadata.name == plugin_name:
            return plugin
    return None


def emit_observability_hook(
    *,
    runtime: PluginRuntime | None,
    event: str,
    run_context: dict[str, Any],
    payload: dict[str, Any] | None = None,
    out_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> None:
    if runtime is None:
        return
    payload = payload or {}
    for plugin in get_plugins_by_type(runtime, "observability"):
        if not isinstance(plugin, ObservabilityExporterPlugin):
            continue
        try:
            if event == "on_run_started":
                plugin.on_run_started(run_context)
            elif event == "on_run_completed":
                plugin.on_run_completed(run_context, payload)
            elif event == "on_gate_failed":
                plugin.on_gate_failed(run_context, payload)
        except Exception as exc:  # noqa: BLE001
            if logger is not None and out_dir is not None:
                _handle_plugin_exception(
                    runtime=runtime,
                    out_dir=out_dir,
                    plugin=plugin,
                    stage=HOOKS.observability,
                    exc=exc,
                    logger=logger,
                )


def execute_plugins(
    *,
    runtime: PluginRuntime,
    run_id: str,
    out_dir: Path,
    changeset_path: Path,
    changeset_raw: dict[str, Any],
    manifest_payload: dict[str, Any],
    compare_data: dict[str, Any],
    replay_data: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    for plugin in runtime.active_plugins:
        context = _build_context(
            runtime=runtime,
            run_id=run_id,
            out_dir=out_dir,
            changeset_path=changeset_path,
            changeset_raw=changeset_raw,
            manifest_payload=manifest_payload,
            phase=HOOKS.execute,
        )
        payload = {
            "compare_data": compare_data,
            "replay_data": replay_data,
            "manifest": manifest_payload,
        }
        try:
            output = plugin.execute(context, payload)
            normalized_output = normalize_plugin_payload(output if isinstance(output, dict) else {"value": output})
            artifact_dir = _write_plugin_artifact(
                runtime=runtime,
                out_dir=out_dir,
                plugin=plugin,
                phase=HOOKS.execute,
                payload=normalized_output,
            )
            result = PluginResult(
                plugin=plugin.metadata.name,
                plugin_type=plugin.metadata.plugin_type,
                status="ok",
                phase=context.phase,
                optional=not bool(plugin.required),
                capabilities=plugin.metadata.capabilities,
                outputs=normalized_output,
                artifact_dir=artifact_dir,
            )
        except Exception as exc:  # noqa: BLE001
            _handle_plugin_exception(
                runtime=runtime,
                out_dir=out_dir,
                plugin=plugin,
                stage=HOOKS.execute,
                exc=exc,
                logger=logger,
            )
            result = PluginResult(
                plugin=plugin.metadata.name,
                plugin_type=plugin.metadata.plugin_type,
                status="error",
                phase=context.phase,
                optional=not bool(plugin.required),
                capabilities=plugin.metadata.capabilities,
                outputs={},
                error=str(exc),
            )
        runtime.results.append(result.to_dict())

    return {
        "enabled": runtime.enabled,
        "loaded_plugins": runtime.manifest.loaded_plugins,
        "failed_plugins": runtime.manifest.failed_plugins,
        "warnings": runtime.manifest.warnings,
        "output_artifacts": runtime.manifest.output_artifacts,
        "results": runtime.results,
        "issues": runtime.issues,
    }


def cleanup_plugins(
    *,
    runtime: PluginRuntime,
    run_id: str,
    out_dir: Path,
    changeset_path: Path,
    changeset_raw: dict[str, Any],
    manifest_payload: dict[str, Any],
    logger: logging.Logger,
) -> None:
    for plugin in runtime.initialized_plugins:
        context = _build_context(
            runtime=runtime,
            run_id=run_id,
            out_dir=out_dir,
            changeset_path=changeset_path,
            changeset_raw=changeset_raw,
            manifest_payload=manifest_payload,
            phase=HOOKS.cleanup,
        )
        try:
            plugin.cleanup(context)
        except Exception as exc:  # noqa: BLE001
            _handle_plugin_exception(
                runtime=runtime,
                out_dir=out_dir,
                plugin=plugin,
                stage=HOOKS.cleanup,
                exc=exc,
                logger=logger,
            )
