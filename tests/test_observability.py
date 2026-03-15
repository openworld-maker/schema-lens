from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from schema_lens.observability import (
    OTelRecorder,
    WebhookEmitter,
    build_event,
    build_metrics_from_compare,
    validate_event,
)


def test_event_schema_validation():
    event = build_event(
        event_type="run_started",
        timestamp="2026-03-15T22:00:00Z",
        run_id="r1",
        payload={"k": 10},
    )
    validate_event(event)


def test_prometheus_metrics_emission():
    compare_data = {
        "diffs": [{"risk_severity": "HIGH"}, {"risk_severity": "LOW"}],
        "performance": {
            "overall": {
                "baseline_client_latency_ms": {"p95": 100},
                "shadow_client_latency_ms": {"p95": 120},
            },
            "caches": {"filterCache": {"evictions": {"delta_pct": 15.0}}},
        },
    }
    prom = build_metrics_from_compare(compare_data, failed=False)
    text = prom.render_text()
    assert "schema_lens_runs_total" in text
    assert "schema_lens_high_risk_queries_total 1.0" in text
    assert "schema_lens_p95_latency_regression_pct 20.0" in text


def test_otel_noop_fallback():
    rec = OTelRecorder(enabled=False)
    rec.start_span("replay", name="replay", started_at="t1", attributes={"run_id": "r1"})
    rec.end_span("replay", ended_at="t2")
    assert rec.export()["spans"] == []


def test_webhook_payload_delivery():
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            received.append(json.loads(body.decode("utf-8")))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        emitter = WebhookEmitter(enabled=True, urls=[f"http://127.0.0.1:{port}/events"])
        event = build_event(
            event_type="run_completed",
            timestamp="2026-03-15T22:00:00Z",
            run_id="r-123",
            payload={"status": "succeeded"},
        )
        deliveries = emitter.emit(event)
        assert deliveries[0]["ok"] is True
        assert received[0]["event_type"] == "run_completed"
    finally:
        server.shutdown()
        server.server_close()
