"""Run lifecycle hook names for plugin execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginHookPhase:
    validate: str = "validate"
    initialize: str = "initialize"
    query_source: str = "query_source"
    doc_source: str = "doc_source"
    replay: str = "replay"
    analyze: str = "analyze"
    gate: str = "gate"
    report: str = "report"
    observability: str = "observability"
    rollout: str = "rollout"
    execute: str = "execute"
    cleanup: str = "cleanup"


HOOKS = PluginHookPhase()

