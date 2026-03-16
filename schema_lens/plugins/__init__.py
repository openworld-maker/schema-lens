"""SolrGuard plugin SDK."""

from schema_lens.plugins.base import BasePlugin, PluginContext, PluginMetadata, PluginResult
from schema_lens.plugins.hooks import HOOKS, PluginHookPhase
from schema_lens.plugins.loader import (
    LoadedPlugins,
    PluginRuntimeConfig,
    load_plugin_runtime_config,
    load_plugins,
    validate_issues,
)
from schema_lens.plugins.manifest import PluginArtifactPaths, PluginRunManifest
from schema_lens.plugins.registry import PluginRegistry

__all__ = [
    "BasePlugin",
    "PluginContext",
    "PluginMetadata",
    "PluginResult",
    "PluginRuntimeConfig",
    "PluginRegistry",
    "LoadedPlugins",
    "PluginArtifactPaths",
    "PluginRunManifest",
    "HOOKS",
    "PluginHookPhase",
    "load_plugin_runtime_config",
    "load_plugins",
    "validate_issues",
]
