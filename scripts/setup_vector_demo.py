#!/usr/bin/env python3
"""Prepare a SolrCloud vector demo collection/configset and index sample embeddings."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import httpx

SOLR_URL = "http://localhost:8983/solr"
COLLECTION = "products_vector"
CONFIGSET_PREFIX = "products_vector_v1"

ROOT = Path(__file__).resolve().parents[1]
CONFIGSET_DIR = ROOT / "examples/solrcloud-docker/configsets/products_vector"
DOCS = ROOT / "examples/vectors/embeddings_small.jsonl"


def _zip_dir(path: Path) -> bytes:
    archive_root = path
    if not (archive_root / "solrconfig.xml").exists() and (
        archive_root / "conf" / "solrconfig.xml"
    ).exists():
        archive_root = archive_root / "conf"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        files = sorted([p for p in archive_root.rglob("*") if p.is_file()])
        for file_path in files:
            zf.write(file_path, arcname=file_path.relative_to(archive_root).as_posix())
    return buffer.getvalue()


def _read_docs(path: Path) -> list[dict]:
    docs: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        docs.append(json.loads(line))
    return docs


def _configset_names(config_zip: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(config_zip).hexdigest()[:8]
    configset = f"{CONFIGSET_PREFIX}_{digest}"
    return configset, f"{configset}__trusted"


def main() -> None:
    config_zip = _zip_dir(CONFIGSET_DIR)
    configset, configset_trusted = _configset_names(config_zip)

    with httpx.Client(timeout=60.0) as client:
        for endpoint, name in (
            ("collections", COLLECTION),
            ("configs", configset_trusted),
            ("configs", configset),
        ):
            client.get(
                f"{SOLR_URL}/admin/{endpoint}",
                params={"action": "DELETE", "name": name, "wt": "json"},
            )

        upload = client.post(
            f"{SOLR_URL}/admin/configs",
            params={
                "action": "UPLOAD",
                "name": configset,
                "overwrite": "true",
                "cleanup": "true",
                "wt": "json",
            },
            content=config_zip,
            headers={"Content-Type": "application/octet-stream"},
        )
        upload.raise_for_status()

        config_name = configset
        promote = client.get(
            f"{SOLR_URL}/admin/configs",
            params={
                "action": "CREATE",
                "name": configset_trusted,
                "baseConfigSet": configset,
                "configSetProp.trusted": "true",
                "wt": "json",
            },
        )
        if promote.status_code < 400:
            config_name = configset_trusted

        create = client.get(
            f"{SOLR_URL}/admin/collections",
            params={
                "action": "CREATE",
                "name": COLLECTION,
                "numShards": "1",
                "replicationFactor": "1",
                "collection.configName": config_name,
                "wt": "json",
            },
        )
        create.raise_for_status()

        docs = _read_docs(DOCS)
        ingest = client.post(
            f"{SOLR_URL}/{COLLECTION}/update",
            params={"commit": "true", "wt": "json"},
            json=docs,
        )
        ingest.raise_for_status()

    print(f"Prepared vector collection '{COLLECTION}' with configset '{config_name}'")


if __name__ == "__main__":
    main()
