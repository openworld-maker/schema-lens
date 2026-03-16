"""Diff and root-cause analyzer plugin contracts."""

from __future__ import annotations

from typing import Any

from schema_lens.plugins.base import BasePlugin


class DiffAnalyzerPlugin(BasePlugin):
    """Analyze compare outputs and emit extra diff context."""

    def analyze(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        return {}

    def get_report_section(self, analysis_result: dict[str, Any]) -> dict[str, Any]:
        return {}


class RootCauseRulePlugin(BasePlugin):
    """Add root-cause decision logic."""

    def classify(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        return {}


class RecommendationRulePlugin(BasePlugin):
    """Generate recommendation hints from findings."""

    def recommend(self, run_context: dict[str, Any], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
        return []
