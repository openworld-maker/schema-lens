#!/usr/bin/env python3
"""Create a procurement demo baseline collection with synonym/stopword aware configset."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx

SOLR_URL = "http://localhost:8983/solr"
COLLECTION = "procurement"
CONFIGSET = "procurement_v1"
CONFIGSET_TRUSTED = f"{CONFIGSET}__trusted"

ROOT = Path(__file__).resolve().parents[1]
CONFIGSET_DIR = ROOT / "examples/configsets/procurement_v1"
DOCS = ROOT / "examples/docs/procurement_docs.jsonl"


def _admin_get(client: httpx.Client, params: dict[str, str]) -> dict:
    response = client.get(f"{SOLR_URL}/admin/collections", params={**params, "wt": "json"})
    if response.status_code >= 400:
        raise RuntimeError(
            f"Collections API failed ({response.status_code}) params={params}: {response.text}"
        )
    return response.json()


def _configs_get(client: httpx.Client, params: dict[str, str]) -> dict:
    response = client.get(f"{SOLR_URL}/admin/configs", params={**params, "wt": "json"})
    if response.status_code >= 400:
        raise RuntimeError(
            f"ConfigSets API failed ({response.status_code}) params={params}: {response.text}"
        )
    return response.json()


def _delete_if_exists(client: httpx.Client) -> None:
    for action, name in (
        ("collections", COLLECTION),
        ("configs", CONFIGSET_TRUSTED),
        ("configs", CONFIGSET),
    ):
        endpoint = "admin/collections" if action == "collections" else "admin/configs"
        params = {"action": "DELETE", "name": name, "wt": "json"}
        resp = client.get(f"{SOLR_URL}/{endpoint}", params=params)
        if resp.status_code >= 400:
            continue


def _locate_configset_root(path: Path) -> Path:
    if (path / "conf").exists():
        return path
    children = [child for child in path.iterdir() if child.is_dir()]
    if len(children) == 1 and (children[0] / "conf").exists():
        return children[0]
    conf_matches = [match for match in path.rglob("conf") if match.is_dir()]
    if len(conf_matches) == 1:
        return conf_matches[0].parent
    raise RuntimeError(f"Could not locate configset root under {path}")


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
    docs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        docs.append(json.loads(line))
    return docs


def main() -> None:
    with httpx.Client(timeout=30.0) as client:
        _delete_if_exists(client)

        cfg_root = _locate_configset_root(CONFIGSET_DIR)
        upload = client.post(
            f"{SOLR_URL}/admin/configs",
            params={
                "action": "UPLOAD",
                "name": CONFIGSET,
                "overwrite": "true",
                "cleanup": "true",
                "wt": "json",
            },
            content=_zip_dir(cfg_root),
            headers={"Content-Type": "application/octet-stream"},
        )
        upload.raise_for_status()

        config_name = CONFIGSET
        try:
            _configs_get(
                client,
                {
                    "action": "CREATE",
                    "name": CONFIGSET_TRUSTED,
                    "baseConfigSet": CONFIGSET,
                    "configSetProp.trusted": "true",
                },
            )
            config_name = CONFIGSET_TRUSTED
        except RuntimeError:
            config_name = CONFIGSET

        _admin_get(
            client,
            {
                "action": "CREATE",
                "name": COLLECTION,
                "numShards": "1",
                "replicationFactor": "1",
                "collection.configName": config_name,
            },
        )

        docs = _read_docs(DOCS)
        ingest = client.post(
            f"{SOLR_URL}/{COLLECTION}/update",
            params={"commit": "true", "wt": "json"},
            json=docs,
        )
        ingest.raise_for_status()

    print(f"Prepared collection '{COLLECTION}' with configset '{config_name}'")


if __name__ == "__main__":
    main()
