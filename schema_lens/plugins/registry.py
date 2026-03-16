"""Plugin registry for discovered plugin instances."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from schema_lens.plugins.base import BasePlugin
from schema_lens.plugins.errors import PluginConfigurationError


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


@dataclass
class RegistrySelection:
    plugins: list[BasePlugin]
    missing_required: list[str]


class PluginRegistry:
    """In-memory plugin registry keyed by plugin name."""

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._by_type: dict[str, list[str]] = defaultdict(list)

    def register(self, plugin: BasePlugin) -> None:
        meta = getattr(plugin, "metadata", None)
        if meta is None:
            raise PluginConfigurationError("plugin missing metadata")
        if not meta.name or not meta.plugin_type:
            raise PluginConfigurationError("plugin metadata requires non-empty name and plugin_type")
        if meta.name in self._plugins:
            raise PluginConfigurationError(f"duplicate plugin name: {meta.name}")
        self._plugins[meta.name] = plugin
        self._by_type[meta.plugin_type].append(meta.name)

    def all(self) -> list[BasePlugin]:
        return [self._plugins[name] for name in sorted(self._plugins)]

    def by_type(self, plugin_type: str) -> list[BasePlugin]:
        names = self._by_type.get(plugin_type, [])
        return [self._plugins[name] for name in names]

    def get_by_type(self, plugin_type: str) -> list[BasePlugin]:
        return self.by_type(plugin_type)

    def get_by_name(self, name: str) -> BasePlugin | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict[str, object]]:
        plugins: list[dict[str, object]] = []
        for plugin in self.all():
            plugins.append(
                {
                    "name": plugin.metadata.name,
                    "version": plugin.metadata.version,
                    "description": plugin.metadata.description,
                    "plugin_type": plugin.metadata.plugin_type,
                    "compatible_schema_lens_version": plugin.metadata.compatible_schema_lens_version,
                    "capabilities": list(plugin.metadata.capabilities),
                    "required": bool(plugin.required),
                }
            )
        return plugins

    def validate_plugin_compatibility(self, current_version: str) -> list[str]:
        incompatible: list[str] = []
        for plugin in self.all():
            requirement = plugin.metadata.compatible_schema_lens_version
            if _version_satisfies(current_version, requirement):
                continue
            incompatible.append(plugin.metadata.name)
        return incompatible

    def resolve(self, enable: list[str] | None, disable: list[str]) -> RegistrySelection:
        if enable:
            selected_names = [name for name in enable if name in self._plugins]
        else:
            selected_names = [name for name in sorted(self._plugins) if name not in disable]

        plugins = [self._plugins[name] for name in selected_names]
        missing_required = [name for name in (enable or []) if name not in self._plugins]
        return RegistrySelection(plugins=plugins, missing_required=missing_required)

    def __iter__(self) -> Iterable[BasePlugin]:
        yield from self.all()
