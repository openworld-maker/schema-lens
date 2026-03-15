"""Policy bundle loading and composition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_policy_bundle(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"policy bundle must be an object: {path}")
    return payload


def merge_policy_bundles(bundle_paths: list[Path]) -> dict[str, Any]:
    merged: dict[str, Any] = {"fail": [], "warn": [], "metadata": {}}
    for path in bundle_paths:
        data = load_policy_bundle(path)
        fail_rules = data.get("fail", [])
        warn_rules = data.get("warn", [])
        metadata = data.get("metadata", {})
        if isinstance(fail_rules, list):
            merged["fail"].extend(fail_rules)
        if isinstance(warn_rules, list):
            merged["warn"].extend(warn_rules)
        if isinstance(metadata, dict):
            merged["metadata"].update(metadata)
    return merged
