"""Schema Lens plugin SDK."""

from schema_lens.plugins.base import BasePlugin, PluginContext, PluginMetadata, PluginResult
from schema_lens.plugins.loader import (
    LoadedPlugins,
    PluginRuntimeConfig,
    load_plugin_runtime_config,
    load_plugins,
    validate_issues,
)
from schema_lens.plugins.registry import PluginRegistry

__all__ = [
    "BasePlugin",
    "PluginContext",
    "PluginMetadata",
    "PluginResult",
    "PluginRuntimeConfig",
    "PluginRegistry",
    "LoadedPlugins",
    "load_plugin_runtime_config",
    "load_plugins",
    "validate_issues",
]
