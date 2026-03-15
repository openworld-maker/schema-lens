"""Plugin registry for discovered plugin instances."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from schema_lens.plugins.base import BasePlugin
from schema_lens.plugins.errors import PluginConfigurationError


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
