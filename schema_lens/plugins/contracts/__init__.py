"""Plugin extension-point contracts."""

from schema_lens.plugins.contracts.analyzer import (
    DiffAnalyzerPlugin,
    RecommendationRulePlugin,
    RootCauseRulePlugin,
)
from schema_lens.plugins.contracts.auth import AuthProviderPlugin
from schema_lens.plugins.contracts.doc_source import DocSourcePlugin
from schema_lens.plugins.contracts.gate import GateEvaluatorPlugin
from schema_lens.plugins.contracts.observability import ObservabilityExporterPlugin
from schema_lens.plugins.contracts.query_source import QuerySourcePlugin
from schema_lens.plugins.contracts.report import ReportRendererPlugin, ReportWidgetPlugin
from schema_lens.plugins.contracts.replay import ReplayExecutorPlugin
from schema_lens.plugins.contracts.rollout import RolloutProviderPlugin

__all__ = [
    "AuthProviderPlugin",
    "QuerySourcePlugin",
    "DocSourcePlugin",
    "ReplayExecutorPlugin",
    "DiffAnalyzerPlugin",
    "RootCauseRulePlugin",
    "RecommendationRulePlugin",
    "GateEvaluatorPlugin",
    "ReportRendererPlugin",
    "ReportWidgetPlugin",
    "ObservabilityExporterPlugin",
    "RolloutProviderPlugin",
]
