from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schema_lens.observability import OTelRecorder, WebhookEmitter, build_event, validate_event


@dataclass
class ObservabilityRuntime:
    config: dict[str, Any]
    otel: OTelRecorder
    webhooks: WebhookEmitter
    events: list[dict[str, Any]] = field(default_factory=list)
    webhook_deliveries: list[dict[str, Any]] = field(default_factory=list)


def initialize_observability(
    *,
    changeset_raw: dict[str, Any],
    manifest_settings: dict[str, Any],
) -> ObservabilityRuntime:
    raw_obs = changeset_raw.get("observability", {})
    observability_cfg = raw_obs if isinstance(raw_obs, dict) else {}
    prometheus_cfg = (
        observability_cfg.get("prometheus", {})
        if isinstance(observability_cfg.get("prometheus"), dict)
        else {}
    )
    otel_cfg = (
        observability_cfg.get("otel", {}) if isinstance(observability_cfg.get("otel"), dict) else {}
    )
    webhook_cfg = (
        observability_cfg.get("webhooks", {})
        if isinstance(observability_cfg.get("webhooks"), dict)
        else {}
    )

    runtime = ObservabilityRuntime(
        config=observability_cfg,
        otel=OTelRecorder(enabled=bool(observability_cfg.get("enabled", False) and otel_cfg.get("enabled", False))),
        webhooks=WebhookEmitter(
            enabled=bool(observability_cfg.get("enabled", False) and webhook_cfg.get("enabled", False)),
            urls=[str(u) for u in webhook_cfg.get("urls", []) if isinstance(u, str)],
            headers={
                str(k): str(v)
                for k, v in (webhook_cfg.get("headers", {}) or {}).items()
                if isinstance(k, str)
            }
            if isinstance(webhook_cfg.get("headers"), dict)
            else {},
            timeout_seconds=float(webhook_cfg.get("timeout_seconds", 3.0)),
        ),
    )

    manifest_settings["observability"] = {
        "enabled": bool(observability_cfg.get("enabled", False)),
        "prometheus": {"enabled": bool(prometheus_cfg.get("enabled", False))},
        "otel": {"enabled": bool(otel_cfg.get("enabled", False))},
        "webhooks": {
            "enabled": bool(webhook_cfg.get("enabled", False)),
            "targets": len([u for u in webhook_cfg.get("urls", []) if isinstance(u, str)]),
        },
    }
    return runtime


def emit_observability_event(
    runtime: ObservabilityRuntime,
    *,
    event_type: str,
    timestamp: str,
    run_id: str,
    payload: dict[str, Any],
) -> None:
    if not bool(runtime.config.get("enabled", False)):
        return
    event = build_event(
        event_type=event_type,
        timestamp=timestamp,
        run_id=run_id,
        payload=payload,
    )
    validate_event(event)
    runtime.events.append(event)
    runtime.webhook_deliveries.extend(runtime.webhooks.emit(event))
