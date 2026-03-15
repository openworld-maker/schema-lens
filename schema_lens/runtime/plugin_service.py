from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schema_lens.errors import StageError
from schema_lens.plugins import (
    PluginContext,
    PluginResult,
    load_plugin_runtime_config,
    load_plugins,
    validate_issues,
)


@dataclass
class PluginRuntime:
    enabled: bool
    strict: bool
    active_plugins: list[Any] = field(default_factory=list)
    initialized_plugins: list[Any] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


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
    validate_issues(loaded_plugins.issues, strict=plugin_cfg.strict)

    runtime = PluginRuntime(
        enabled=plugin_cfg.enabled,
        strict=plugin_cfg.strict,
        issues=issues,
        settings={
            "enabled": plugin_cfg.enabled,
            "strict": plugin_cfg.strict,
            "entry_points": plugin_cfg.enable_entry_points,
            "entry_point_group": plugin_cfg.entry_point_group,
            "plugin_paths": plugin_cfg.plugin_paths,
            "enable_plugins": plugin_cfg.enable_plugins,
            "disable_plugins": plugin_cfg.disable_plugins,
            "loaded": [
                {
                    "name": plugin.metadata.name,
                    "version": plugin.metadata.version,
                    "plugin_type": plugin.metadata.plugin_type,
                    "capabilities": plugin.metadata.capabilities,
                    "required": bool(plugin.required),
                }
                for plugin in loaded_plugins.active
            ],
            "issues": issues,
        },
    )

    for plugin in loaded_plugins.active:
        context = PluginContext(
            run_id=run_id,
            out_dir=out_dir.resolve(),
            changeset_path=changeset_path.resolve(),
            changeset=changeset_raw,
            manifest=manifest_payload,
            strict=plugin_cfg.strict,
            phase="initialize",
        )
        try:
            plugin.validate(context)
            plugin.initialize(context)
            runtime.active_plugins.append(plugin)
            runtime.initialized_plugins.append(plugin)
        except Exception as exc:  # noqa: BLE001
            issue = {
                "plugin": plugin.metadata.name,
                "stage": "initialize",
                "message": str(exc),
                "fatal": plugin_cfg.strict,
            }
            runtime.issues.append(issue)
            if plugin_cfg.strict:
                raise StageError(f"plugin initialize failed ({plugin.metadata.name}): {exc}") from exc
            logger.warning("Plugin initialize failed for %s: %s", plugin.metadata.name, exc)

    return runtime


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
        context = PluginContext(
            run_id=run_id,
            out_dir=out_dir.resolve(),
            changeset_path=changeset_path.resolve(),
            changeset=changeset_raw,
            manifest=manifest_payload,
            strict=runtime.strict,
            phase="finalize",
        )
        payload = {
            "compare_data": compare_data,
            "replay_data": replay_data,
            "manifest": manifest_payload,
        }
        try:
            output = plugin.execute(context, payload)
            result = PluginResult(
                plugin=plugin.metadata.name,
                plugin_type=plugin.metadata.plugin_type,
                status="ok",
                phase=context.phase,
                optional=not bool(plugin.required),
                capabilities=plugin.metadata.capabilities,
                outputs=output if isinstance(output, dict) else {"value": output},
            )
        except Exception as exc:  # noqa: BLE001
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
            runtime.issues.append(
                {
                    "plugin": plugin.metadata.name,
                    "stage": "execute",
                    "message": str(exc),
                    "fatal": runtime.strict,
                }
            )
            if runtime.strict:
                raise StageError(f"plugin execute failed ({plugin.metadata.name}): {exc}") from exc
            logger.warning("Plugin execute failed for %s: %s", plugin.metadata.name, exc)
        runtime.results.append(result.to_dict())

    return {
        "enabled": runtime.enabled,
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
        context = PluginContext(
            run_id=run_id,
            out_dir=out_dir.resolve(),
            changeset_path=changeset_path.resolve(),
            changeset=changeset_raw,
            manifest=manifest_payload,
            strict=runtime.strict,
            phase="cleanup",
        )
        try:
            plugin.cleanup(context)
        except Exception as exc:  # noqa: BLE001
            runtime.issues.append(
                {
                    "plugin": plugin.metadata.name,
                    "stage": "cleanup",
                    "message": str(exc),
                    "fatal": False,
                }
            )
            logger.warning("Plugin cleanup failed for %s: %s", plugin.metadata.name, exc)
