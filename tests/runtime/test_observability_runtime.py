from __future__ import annotations

from schema_lens.runtime.observability_service import (
    emit_observability_event,
    initialize_observability,
)
from schema_lens.runtime.report_finalize_service import finalize_observability_outputs


class _OtelStub:
    def export(self):
        return {"spans": [{"name": "snapshot"}]}


class _ObsRuntimeStub:
    def __init__(self) -> None:
        self.events = [{"event_type": "run_started"}]
        self.webhook_deliveries = [{"url": "http://example.test", "ok": True}]
        self.otel = _OtelStub()


def test_initialize_observability_and_emit_event() -> None:
    settings: dict[str, object] = {}
    runtime = initialize_observability(
        changeset_raw={
            "observability": {
                "enabled": True,
                "otel": {"enabled": True},
                "webhooks": {"enabled": False},
            }
        },
        manifest_settings=settings,
    )
    assert settings["observability"]["enabled"] is True

    emit_observability_event(
        runtime,
        event_type="run_started",
        timestamp="2026-03-15T22:00:00Z",
        run_id="r1",
        payload={"k": 10},
    )
    assert len(runtime.events) == 1
    assert runtime.events[0]["event_type"] == "run_started"


def test_finalize_observability_outputs_enabled(tmp_path):
    outputs = {
        "observability_events_jsonl": str(tmp_path / "events.jsonl"),
        "otel_spans_json": str(tmp_path / "otel.json"),
        "webhook_deliveries_json": str(tmp_path / "deliveries.json"),
        "prometheus_metrics_txt": str(tmp_path / "metrics.prom"),
    }

    summary = finalize_observability_outputs(
        observability_runtime=_ObsRuntimeStub(),
        observability_cfg={"enabled": True, "prometheus": {"enabled": False}},
        compare_data={},
        failed=False,
        outputs=outputs,
    )

    assert summary["enabled"] is True
    assert summary["events"] == 1
