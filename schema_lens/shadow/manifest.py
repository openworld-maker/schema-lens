"""Shadow manifest model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ShadowManifest:
    shadow_collection: str
    shadow_solr_url: str
    created_at: str
    applied_changes: list[dict[str, Any]] = field(default_factory=list)
    baseline_collection: str = ""
    baseline_solr_url: str = ""
    shadow_configset: str | None = None
    baseline_configset: str | None = None
    configset_isolated: bool = True
    warnings: list[str] = field(default_factory=list)
    docs_indexed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
