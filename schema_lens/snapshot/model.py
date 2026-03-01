"""Snapshot model definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SnapshotManifest:
    snapshot_version: int
    created_at: str
    solr_url: str
    collection: str
    solr_version: str | None
    request_defaults: dict[str, Any] = field(default_factory=dict)
    schema_path: str = "snapshot.schema.json"
    system_path: str = "snapshot.system.json"
    collection_path: str = "snapshot.collection.json"
    hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

