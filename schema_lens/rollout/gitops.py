"""GitOps-style configset drift detection."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.collections_api import collection_config_name
from schema_lens.solr.configsets_api import download_configset_archive


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _walk_local_hashes(configset_dir: Path) -> dict[str, str]:
    base = configset_dir
    if (base / "conf").exists() and (base / "conf").is_dir():
        base = base / "conf"
    files = sorted([p for p in base.rglob("*") if p.is_file()])
    return {str(p.relative_to(base).as_posix()): _hash_file(p) for p in files}


def compare_git_vs_live_configset(
    *,
    client: SolrHttpClient,
    collection: str,
    local_configset_dir: Path,
) -> dict[str, Any]:
    config_name = collection_config_name(client, collection)
    archive = download_configset_archive(client, config_name)
    local_hash = _hash_bytes(b"".join(sorted(f"{k}:{v}".encode("utf-8") for k, v in _walk_local_hashes(local_configset_dir).items())))
    live_hash = _hash_bytes(archive)
    return {
        "collection": collection,
        "configset": config_name,
        "local_configset_dir": str(local_configset_dir.resolve()),
        "local_hash": local_hash,
        "live_archive_hash": live_hash,
        "drift_detected": local_hash != live_hash,
    }
