"""Explain compatibility adapter."""

from __future__ import annotations

from typing import Any


def structured_explain_supported(caps: dict[str, Any]) -> bool:
    return bool(caps.get("structured_explain_supported", False))


def extract_explain_debug(debug_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize explain/parsed query from different Solr debug payload variants."""
    payload = debug_payload if isinstance(debug_payload, dict) else {}
    debug = payload.get("debug") if isinstance(payload.get("debug"), dict) else payload

    parsed = debug.get("parsedquery_toString") or debug.get("parsedquery")
    explain_block = debug.get("explain")
    structured = explain_block if isinstance(explain_block, dict) else None

    if structured is None and isinstance(explain_block, list):
        mapped: dict[str, Any] = {}
        for item in explain_block:
            if isinstance(item, dict):
                mapped.update(item)
        structured = mapped if mapped else None

    raw_explain = explain_block if isinstance(explain_block, (str, list, dict)) else None

    return {
        "parsedquery": parsed,
        "structured_explain": structured,
        "raw_explain": raw_explain,
    }
