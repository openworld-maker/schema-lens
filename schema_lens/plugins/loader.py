"""Plugin discovery and compatibility checks."""

from __future__ import annotations

import importlib.metadata
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from schema_lens import __version__
from schema_lens.plugins.base import BasePlugin
from schema_lens.plugins.errors import (
    PluginCompatibilityError,
    PluginConfigurationError,
    PluginIssue,
)
from schema_lens.plugins.registry import PluginRegistry, RegistrySelection


@dataclass
class PluginRuntimeConfig:
    enabled: bool = False
    directories: list[str] = field(default_factory=list)
    load_builtin: bool = True
    enabled_plugins: list[str] = field(default_factory=list)
    strict_mode: bool = False
    config: dict[str, dict[str, Any]] = field(default_factory=dict)
    enable_entry_points: bool = True
    entry_point_group: str = "schema_lens.plugins"

    @property
    def plugin_paths(self) -> list[str]:
        """Backward-compatible alias."""
        return self.directories

    @property
    def strict(self) -> bool:
        """Backward-compatible alias."""
        return self.strict_mode

    @property
    def enable_plugins(self) -> list[str]:
        """Backward-compatible alias."""
        return self.enabled_plugins

    @property
    def disable_plugins(self) -> list[str]:
        """Backward-compatible alias for removed setting."""
        return []


@dataclass
class LoadedPlugins:
    config: PluginRuntimeConfig
    registry: PluginRegistry
    active: list[BasePlugin]
    issues: list[PluginIssue]


def _parse_version(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    values: list[int] = []
    for part in parts[:3]:
        number = "".join(ch for ch in part if ch.isdigit())
        values.append(int(number) if number else 0)
    while len(values) < 3:
        values.append(0)
    return tuple(values)  # type: ignore[return-value]


def _version_satisfies(current: str, requirement: str) -> bool:
    req = requirement.strip()
    if not req or req == "*":
        return True
    current_tuple = _parse_version(current)
    for token in [piece.strip() for piece in req.split(",") if piece.strip()]:
        op = None
        for candidate in (">=", "<=", "==", "!=", ">", "<"):
            if token.startswith(candidate):
                op = candidate
                raw = token[len(candidate) :].strip()
                break
        if op is None:
            op = "=="
            raw = token
        target = _parse_version(raw)
        if op == ">=" and not (current_tuple >= target):
            return False
        if op == "<=" and not (current_tuple <= target):
            return False
        if op == ">" and not (current_tuple > target):
            return False
        if op == "<" and not (current_tuple < target):
            return False
        if op == "==" and not (current_tuple == target):
            return False
        if op == "!=" and not (current_tuple != target):
            return False
    return True


def _coerce_plugin(candidate: Any) -> BasePlugin:
    if isinstance(candidate, BasePlugin):
        return candidate
    if isinstance(candidate, type) and issubclass(candidate, BasePlugin):
        return candidate()
    if callable(candidate):
        created = candidate()
        if isinstance(created, BasePlugin):
            return created
    raise PluginConfigurationError(f"Unsupported plugin object: {candidate!r}")


def _register_from_module(module: ModuleType, registry: PluginRegistry) -> None:
    if hasattr(module, "register_plugins") and callable(module.register_plugins):
        module.register_plugins(registry)
        return

    if hasattr(module, "PLUGINS"):
        raw = getattr(module, "PLUGINS")
        if not isinstance(raw, list):
            raise PluginConfigurationError("PLUGINS must be a list")
        for item in raw:
            registry.register(_coerce_plugin(item))
        return

    if hasattr(module, "PLUGIN"):
        registry.register(_coerce_plugin(getattr(module, "PLUGIN")))
        return

    raise PluginConfigurationError("module must expose register_plugins, PLUGINS or PLUGIN")


def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"schema_lens_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise PluginConfigurationError(f"unable to load plugin module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_builtin_plugins(registry: PluginRegistry) -> list[PluginIssue]:
    issues: list[PluginIssue] = []
    try:
        from schema_lens.plugins.builtin import register_builtin_plugins

        register_builtin_plugins(registry)
    except Exception as exc:  # noqa: BLE001
        issues.append(PluginIssue(plugin="builtin", stage="load", message=str(exc)))
    return issues


def _load_from_entry_points(group: str, registry: PluginRegistry) -> list[PluginIssue]:
    issues: list[PluginIssue] = []
    eps = importlib.metadata.entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    for ep in selected:
        try:
            loaded = ep.load()
            registry.register(_coerce_plugin(loaded))
        except Exception as exc:  # noqa: BLE001
            issues.append(
                PluginIssue(
                    plugin=getattr(ep, "name", "entry_point"),
                    stage="load",
                    message=str(exc),
                )
            )
    return issues


def _iter_plugin_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and not path.name.startswith("_")
    )


def _load_from_plugin_paths(plugin_paths: list[str], base_dir: Path, registry: PluginRegistry) -> list[PluginIssue]:
    issues: list[PluginIssue] = []
    for value in plugin_paths:
        root = Path(value)
        if not root.is_absolute():
            root = (base_dir / root).resolve()
        if not root.exists():
            issues.append(
                PluginIssue(
                    plugin=value,
                    stage="load",
                    message=f"plugin path does not exist: {root}",
                )
            )
            continue

        for file_path in _iter_plugin_files(root):
            try:
                module = _load_module_from_path(file_path)
                _register_from_module(module, registry)
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    PluginIssue(
                        plugin=str(file_path),
                        stage="load",
                        message=str(exc),
                    )
                )
    return issues


def _enforce_compatibility(registry: PluginRegistry) -> list[PluginIssue]:
    issues: list[PluginIssue] = []
    for plugin in registry:
        requirement = plugin.metadata.compatible_schema_lens_version
        if _version_satisfies(__version__, requirement):
            continue
        issues.append(
            PluginIssue(
                plugin=plugin.metadata.name,
                plugin_type=plugin.metadata.plugin_type,
                stage="compatibility",
                message=(
                    f"plugin requires SolrGuard '{requirement}' but runtime is '{__version__}'"
                ),
            )
        )
    return issues


def _read_plugins_config_file(config_path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PluginConfigurationError("plugin config YAML must be a mapping")
    return loaded


def load_plugin_runtime_config(changeset_raw: dict[str, Any], changeset_path: Path) -> PluginRuntimeConfig:
    plugins_cfg = changeset_raw.get("plugins", {})
    if not isinstance(plugins_cfg, dict):
        raise PluginConfigurationError("changeset.plugins must be a mapping")

    merged_cfg: dict[str, Any] = dict(plugins_cfg)
    config_base_dir: Path | None = None
    config_path_raw = plugins_cfg.get("config")
    if isinstance(config_path_raw, str) and config_path_raw:
        config_path = Path(config_path_raw)
        if not config_path.is_absolute():
            config_path = (changeset_path.parent / config_path).resolve()
        config_base_dir = config_path.parent
        loaded = _read_plugins_config_file(config_path)
        merged_cfg = {**loaded, **plugins_cfg}
        if isinstance(loaded.get("config"), dict) and not isinstance(plugins_cfg.get("config"), dict):
            merged_cfg["config"] = loaded["config"]

    directories = merged_cfg.get("directories")
    if directories is None:
        directories = merged_cfg.get("paths", [])
    if not isinstance(directories, list):
        directories = []
    if config_base_dir is not None and "directories" not in plugins_cfg and "paths" not in plugins_cfg:
        adjusted: list[str] = []
        for item in directories:
            if not isinstance(item, str):
                continue
            raw_path = Path(item)
            if raw_path.is_absolute():
                adjusted.append(str(raw_path))
            else:
                adjusted.append(str((config_base_dir / raw_path).resolve()))
        directories = adjusted

    enabled_plugins = merged_cfg.get("enabled_plugins")
    if enabled_plugins is None:
        enabled_plugins = merged_cfg.get("enable_plugins", [])
    if not isinstance(enabled_plugins, list):
        enabled_plugins = []

    strict_mode = merged_cfg.get("strict_mode")
    if strict_mode is None:
        strict_mode = merged_cfg.get("strict", False)

    per_plugin_config = merged_cfg.get("config")
    if isinstance(per_plugin_config, str):
        per_plugin_config = {}
    if not isinstance(per_plugin_config, dict):
        per_plugin_config = {}

    normalized_plugin_config: dict[str, dict[str, Any]] = {}
    for key, value in per_plugin_config.items():
        if isinstance(key, str) and isinstance(value, dict):
            normalized_plugin_config[key] = value

    return PluginRuntimeConfig(
        enabled=bool(merged_cfg.get("enabled", False)),
        directories=[str(item) for item in directories if isinstance(item, str)],
        load_builtin=bool(merged_cfg.get("load_builtin", True)),
        enabled_plugins=[str(item) for item in enabled_plugins if isinstance(item, str)],
        strict_mode=bool(strict_mode),
        config=normalized_plugin_config,
        enable_entry_points=bool(merged_cfg.get("entry_points", True)),
        entry_point_group=str(merged_cfg.get("entry_point_group", "schema_lens.plugins")),
    )


def load_plugins(config: PluginRuntimeConfig, *, base_dir: Path) -> LoadedPlugins:
    registry = PluginRegistry()
    issues: list[PluginIssue] = []

    if not config.enabled:
        return LoadedPlugins(config=config, registry=registry, active=[], issues=issues)

    if config.load_builtin:
        issues.extend(_load_builtin_plugins(registry))

    issues.extend(_load_from_plugin_paths(config.directories, base_dir, registry))
    if config.enable_entry_points:
        issues.extend(_load_from_entry_points(config.entry_point_group, registry))

    issues.extend(_enforce_compatibility(registry))

    incompatible = {issue.plugin for issue in issues if issue.stage == "compatibility"}
    filtered_registry = PluginRegistry()
    for plugin in registry:
        if plugin.metadata.name in incompatible:
            continue
        filtered_registry.register(plugin)

    selection: RegistrySelection = filtered_registry.resolve(
        enable=config.enabled_plugins or None,
        disable=[],
    )
    for name in selection.missing_required:
        issues.append(
            PluginIssue(
                plugin=name,
                stage="selection",
                message="plugin requested in enabled_plugins but not discovered",
                fatal=True,
            )
        )

    return LoadedPlugins(config=config, registry=filtered_registry, active=selection.plugins, issues=issues)


def validate_issues(issues: list[PluginIssue], *, strict: bool) -> None:
    blocking_stages = {"compatibility", "selection", "load"}
    if strict and any(item.fatal or item.stage in blocking_stages for item in issues):
        first = issues[0]
        raise PluginCompatibilityError(f"plugin runtime blocked: {first.message}")
