"""Segment-aware analysis helpers."""

from schema_lens.segments.grouping import aggregate_by_segment
from schema_lens.segments.policy import evaluate_segment_policies
from schema_lens.segments.report import build_segment_report

__all__ = ["aggregate_by_segment", "evaluate_segment_policies", "build_segment_report"]
