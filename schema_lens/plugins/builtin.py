"""Built-in plugin registrations."""

from __future__ import annotations

import importlib

from schema_lens.plugins.registry import PluginRegistry


def register_builtin_plugins(registry: PluginRegistry) -> None:
    """Register first-party plugins shipped with SolrGuard."""
    candidates = (
        ("examples.plugins.sample_query_source.sample_query_source", "SampleQuerySourcePlugin"),
        ("examples.plugins.sample_gate.sample_gate", "SampleGatePlugin"),
        ("examples.plugins.sample_report.sample_report", "SampleReportPlugin"),
    )
    for module_path, class_name in candidates:
        try:
            module = importlib.import_module(module_path)
            plugin_cls = getattr(module, class_name)
            registry.register(plugin_cls())
        except Exception:
            continue
