"""Runtime services used by CLI orchestration."""

from schema_lens.runtime.data_query_service import load_or_extract_queries, load_or_sample_docs
from schema_lens.runtime.governance_service import GovernanceRuntime, finalize_governance_manifest, initialize_governance
from schema_lens.runtime.insight_service import run_ltr_impact, run_recommendations, run_root_cause
from schema_lens.runtime.observability_service import ObservabilityRuntime, emit_observability_event, initialize_observability
from schema_lens.runtime.post_compare_service import (
    build_segment_payload,
    run_explain_flow,
    run_performance_analyze_flow,
    run_rewrite_diff_flow,
    run_vector_flow,
)
from schema_lens.runtime.plugin_service import (
    PluginRuntime,
    cleanup_plugins,
    emit_observability_hook,
    execute_plugins,
    get_plugin_config,
    get_plugins_by_type,
    initialize_plugins,
    plugin_artifact_paths,
    select_plugin,
)
from schema_lens.runtime.privacy_service import PrivacyRuntime, build_and_enforce_privacy_report, initialize_privacy
from schema_lens.runtime.replay_compare_service import run_compare_stage, run_replay_stage
from schema_lens.runtime.report_finalize_service import finalize_observability_outputs, write_report_artifacts
from schema_lens.runtime.security_service import SecurityRuntime, initialize_security
from schema_lens.runtime.snapshot_compat_service import SnapshotCompatRuntime, run_snapshot_and_compat

__all__ = [
    "GovernanceRuntime",
    "SecurityRuntime",
    "PrivacyRuntime",
    "ObservabilityRuntime",
    "PluginRuntime",
    "SnapshotCompatRuntime",
    "initialize_governance",
    "finalize_governance_manifest",
    "initialize_security",
    "initialize_privacy",
    "build_and_enforce_privacy_report",
    "initialize_observability",
    "emit_observability_event",
    "initialize_plugins",
    "get_plugins_by_type",
    "get_plugin_config",
    "select_plugin",
    "plugin_artifact_paths",
    "emit_observability_hook",
    "execute_plugins",
    "cleanup_plugins",
    "run_snapshot_and_compat",
    "write_report_artifacts",
    "finalize_observability_outputs",
    "load_or_sample_docs",
    "load_or_extract_queries",
    "run_replay_stage",
    "run_compare_stage",
    "build_segment_payload",
    "run_vector_flow",
    "run_rewrite_diff_flow",
    "run_explain_flow",
    "run_performance_analyze_flow",
    "run_root_cause",
    "run_recommendations",
    "run_ltr_impact",
]
