from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from schema_lens.observability import build_metrics_from_compare
from schema_lens.report.html_report import render_html_report
from schema_lens.report.json_report import build_report_json
from schema_lens.util.io import write_json, write_jsonl, write_text


def write_report_artifacts(
    *,
    manifest_payload: dict[str, Any],
    compare_data: dict[str, Any],
    replay_data: dict[str, Any],
    report_json_path: Path,
    report_html_path: Path,
    template_dir: Path,
    write_redacted_json: Callable[..., None],
    redact: bool,
    extra_sensitive_keys: list[str],
    plugin_report_sections: dict[str, Any] | None = None,
) -> None:
    report_data = build_report_json(
        manifest=manifest_payload,
        compare_data=compare_data,
        replay_data=replay_data,
        plugin_report_sections=plugin_report_sections or {},
    )
    write_redacted_json(
        report_json_path,
        report_data,
        redact=redact,
        extra_sensitive_keys=extra_sensitive_keys,
    )
    html = render_html_report(report_data, template_dir)
    write_text(report_html_path, html)


def finalize_observability_outputs(
    *,
    observability_runtime,
    observability_cfg: dict[str, Any],
    compare_data: dict[str, Any],
    failed: bool,
    outputs: dict[str, str],
) -> dict[str, Any]:
    if bool(observability_cfg.get("enabled", False)) and observability_runtime is not None:
        write_jsonl(Path(outputs["observability_events_jsonl"]), observability_runtime.events)
        write_json(Path(outputs["otel_spans_json"]), observability_runtime.otel.export())
        write_json(
            Path(outputs["webhook_deliveries_json"]),
            {"deliveries": observability_runtime.webhook_deliveries},
        )

        prometheus_cfg = observability_cfg.get("prometheus", {}) if isinstance(observability_cfg.get("prometheus"), dict) else {}
        if bool(prometheus_cfg.get("enabled", False)):
            prom = build_metrics_from_compare(compare_data, failed=failed)
            write_text(Path(outputs["prometheus_metrics_txt"]), prom.render_text())

        return {
            "enabled": True,
            "events": len(observability_runtime.events),
            "webhook_deliveries": len(observability_runtime.webhook_deliveries),
            "otel_spans": len(observability_runtime.otel.export().get("spans", [])),
        }

    return {
        "enabled": False,
        "reason": "Observability hooks not enabled.",
    }
