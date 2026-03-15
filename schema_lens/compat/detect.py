"""Solr version detection from system info payloads."""

from __future__ import annotations

import re
from typing import Any


_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def detect_solr_version(system_info: dict[str, Any]) -> str | None:
    lucene = system_info.get("lucene", {}) if isinstance(system_info, dict) else {}
    candidates = [
        lucene.get("solr-spec-version"),
        lucene.get("solr-impl-version"),
        system_info.get("solr-spec-version") if isinstance(system_info, dict) else None,
        system_info.get("solr_version") if isinstance(system_info, dict) else None,
    ]
    for value in candidates:
        if not isinstance(value, str):
            continue
        match = _VERSION_RE.search(value)
        if not match:
            continue
        major, minor, patch = match.groups()
        return f"{int(major)}.{int(minor)}.{int(patch or 0)}"
    return None


def parse_major(version: str | None) -> int | None:
    if not isinstance(version, str) or not version:
        return None
    try:
        return int(version.split(".", 1)[0])
    except ValueError:
        return None
