"""Capture and load reproducible baseline snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from schema_lens.compat import compatibility_contract, detect_version_info
from schema_lens.http.client import SolrHttpClient
from schema_lens.snapshot.model import SnapshotManifest
from schema_lens.solr.admin_api import system_info
from schema_lens.solr.collections_api import cluster_status
from schema_lens.solr.schema_api import get_schema
from schema_lens.util.io import ensure_dir, read_json, write_json, write_text
from schema_lens.util.time import utc_now_iso


def snapshot_hash(
    *,
    solr_url: str,
    collection: str,
    schema: dict[str, Any],
    system: dict[str, Any],
    collection_state: dict[str, Any] | None,
    request_defaults: dict[str, Any] | None = None,
) -> str:
    payload = {
        "solr_url": solr_url,
        "collection": collection,
        "schema": schema,
        "system": system,
        "collection_state": collection_state or {},
        "request_defaults": request_defaults or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def capture_snapshot(
    *,
    solr_url: str,
    collection: str,
    out_dir: Path,
    request_defaults: dict[str, Any] | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    ensure_dir(out_dir)

    schema_path = out_dir / "snapshot.schema.json"
    system_path = out_dir / "snapshot.system.json"
    collection_path = out_dir / "snapshot.collection.json"
    manifest_path = out_dir / "snapshot.json"
    hash_path = out_dir / "snapshot.hash.txt"

    client = SolrHttpClient(solr_url, verbose=verbose)
    try:
        schema = get_schema(client, collection)
        system = system_info(client)
        collection_state: dict[str, Any] = {}
        try:
            collection_state = cluster_status(client, collection)
        except Exception:  # noqa: BLE001
            collection_state = {"warning": "Cluster status unavailable"}
    finally:
        client.close()

    snap_hash = snapshot_hash(
        solr_url=solr_url,
        collection=collection,
        schema=schema,
        system=system,
        collection_state=collection_state,
        request_defaults=request_defaults,
    )

    write_json(schema_path, schema)
    write_json(system_path, system)
    write_json(collection_path, collection_state)
    write_text(hash_path, snap_hash + "\n")

    solr_version = (
        system.get("lucene", {}).get("solr-spec-version")
        or system.get("solr_home")
        or None
    )
    manifest = SnapshotManifest(
        snapshot_version=1,
        created_at=utc_now_iso(),
        solr_url=solr_url,
        collection=collection,
        solr_version=str(solr_version) if solr_version is not None else None,
        request_defaults=request_defaults or {},
        schema_path=schema_path.name,
        system_path=system_path.name,
        collection_path=collection_path.name,
        hash=snap_hash,
        compatibility=compatibility_contract(detect_version_info(system), system_info=system),
    )
    write_json(manifest_path, manifest.to_dict())
    return {
        "manifest": manifest.to_dict(),
        "schema": schema,
        "system": system,
        "collection_state": collection_state,
        "paths": {
            "manifest": str(manifest_path.resolve()),
            "schema": str(schema_path.resolve()),
            "system": str(system_path.resolve()),
            "collection": str(collection_path.resolve()),
            "hash": str(hash_path.resolve()),
        },
    }


def load_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    manifest_path = snapshot_dir / "snapshot.json"
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid snapshot manifest: {manifest_path}")

    schema = read_json(snapshot_dir / str(manifest.get("schema_path", "snapshot.schema.json")))
    system = read_json(snapshot_dir / str(manifest.get("system_path", "snapshot.system.json")))
    collection_state = read_json(
        snapshot_dir / str(manifest.get("collection_path", "snapshot.collection.json"))
    )

    computed = snapshot_hash(
        solr_url=str(manifest.get("solr_url")),
        collection=str(manifest.get("collection")),
        schema=schema,
        system=system,
        collection_state=collection_state,
        request_defaults=manifest.get("request_defaults", {}),
    )
    stored = str(manifest.get("hash", ""))
    if stored and computed != stored:
        raise ValueError(f"Snapshot hash mismatch: expected {stored}, computed {computed}")

    return {
        "manifest": manifest,
        "schema": schema,
        "system": system,
        "collection_state": collection_state,
        "hash": computed,
    }
