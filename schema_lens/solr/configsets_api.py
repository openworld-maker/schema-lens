"""Configsets API helpers."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from schema_lens.http.client import SolrHttpClient
from schema_lens.solr.endpoints import configsets_admin_path


def create_configset(
    client: SolrHttpClient,
    name: str,
    base_configset: str,
    configset_props: dict[str, str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "action": "CREATE",
        "name": name,
        "baseConfigSet": base_configset,
        "wt": "json",
    }
    if configset_props:
        for key, value in configset_props.items():
            params[f"configSetProp.{key}"] = value
    return client.get_json(configsets_admin_path(), params=params)


def delete_configset(client: SolrHttpClient, name: str) -> dict[str, Any]:
    return client.get_json(
        configsets_admin_path(),
        params={
            "action": "DELETE",
            "name": name,
            "wt": "json",
        },
    )


def list_configsets(client: SolrHttpClient) -> list[str]:
    payload = client.get_json(
        configsets_admin_path(),
        params={
            "action": "LIST",
            "omitHeader": "true",
            "wt": "json",
        },
    )
    names = payload.get("configSets", [])
    if not isinstance(names, list):
        return []
    return [str(name) for name in names]


def download_configset_archive(client: SolrHttpClient, name: str) -> bytes:
    return client.get_bytes(
        configsets_admin_path(),
        params={
            "action": "DOWNLOAD",
            "name": name,
            "wt": "json",
        },
    )


def extract_configset_archive(archive: bytes, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as zf:
        zf.extractall(out_dir)
    return out_dir


def create_configset_archive(configset_dir: Path) -> bytes:
    if not configset_dir.exists() or not configset_dir.is_dir():
        raise ValueError(f"Configset directory not found: {configset_dir}")

    archive_root = configset_dir
    if not (archive_root / "solrconfig.xml").exists() and (
        archive_root / "conf" / "solrconfig.xml"
    ).exists():
        archive_root = archive_root / "conf"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        files = sorted(
            [path for path in archive_root.rglob("*") if path.is_file()],
            key=lambda p: p.relative_to(archive_root).as_posix(),
        )
        for file_path in files:
            arcname = file_path.relative_to(archive_root).as_posix()
            zf.write(file_path, arcname=arcname)
    return buffer.getvalue()


def upload_configset_archive(
    client: SolrHttpClient,
    name: str,
    archive: bytes,
    *,
    overwrite: bool = True,
    cleanup: bool = True,
) -> dict[str, Any]:
    payload_bytes = client.post_bytes(
        configsets_admin_path(),
        params={
            "action": "UPLOAD",
            "name": name,
            "overwrite": str(bool(overwrite)).lower(),
            "cleanup": str(bool(cleanup)).lower(),
            "wt": "json",
        },
        content_body=archive,
        headers={"Content-Type": "application/octet-stream"},
    )
    text = payload_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"raw": text}


def upload_configset_from_dir(
    client: SolrHttpClient,
    name: str,
    configset_dir: Path,
    *,
    overwrite: bool = True,
    cleanup: bool = True,
) -> dict[str, Any]:
    archive = create_configset_archive(configset_dir)
    return upload_configset_archive(
        client,
        name,
        archive,
        overwrite=overwrite,
        cleanup=cleanup,
    )
