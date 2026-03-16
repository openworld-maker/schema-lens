"""Shadow collection lifecycle manager."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from schema_lens.changesets.apply_schema import apply_schema_operations
from schema_lens.errors import SolrRequestError, ValidationError
from schema_lens.shadow.configset_patcher import (
    apply_configset_updates,
    has_configset_updates,
    hash_directory,
)
from schema_lens.shadow.manifest import ShadowManifest
from schema_lens.shadow.naming import render_shadow_name
from schema_lens.solr.collections_api import (
    collection_config_name,
    create_collection,
    delete_collection,
)
from schema_lens.solr.configsets_api import (
    create_configset,
    delete_configset,
    download_configset_archive,
    extract_configset_archive,
    upload_configset_from_dir,
)
from schema_lens.util.time import utc_now_iso


def _resolve_local_dir(
    raw: str | None,
    *,
    changeset_path: Path | None,
) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() and path.exists():
        return path
    candidates = []
    if changeset_path is not None:
        candidates.append((changeset_path.parent / path).resolve())
    candidates.append((Path.cwd() / path).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else path


def _locate_configset_root(root: Path) -> Path:
    if (root / "conf").exists():
        return root

    children = [path for path in root.iterdir() if path.is_dir()]
    if len(children) == 1 and (children[0] / "conf").exists():
        return children[0]

    matches = [path for path in root.rglob("*") if path.is_dir() and path.name == "conf"]
    if len(matches) == 1:
        return matches[0].parent

    raise ValidationError(
        f"Could not locate configset root under {root}; expected directory containing conf/"
    )


def _materialize_baseline_configset(
    *,
    client: Any,
    baseline_configset: str,
    shadow_cfg: dict[str, Any],
    workspace: Path,
    changeset_path: Path | None,
) -> Path:
    local_dir = _resolve_local_dir(
        str(shadow_cfg.get("baseline_configset_dir"))
        if shadow_cfg.get("baseline_configset_dir") is not None
        else None,
        changeset_path=changeset_path,
    )
    staged = workspace / "configset"
    if local_dir is not None:
        if not local_dir.exists() or not local_dir.is_dir():
            raise ValidationError(f"baseline_configset_dir not found: {local_dir}")
        shutil.copytree(local_dir, staged, dirs_exist_ok=True)
        return _locate_configset_root(staged)

    archive = download_configset_archive(client, baseline_configset)
    extract_configset_archive(archive, staged)
    return _locate_configset_root(staged)


def create_shadow(
    *,
    client: Any,
    baseline_collection: str,
    baseline_solr_url: str,
    shadow_solr_url: str,
    shadow_cfg: dict[str, Any],
    baseline_schema: dict[str, Any],
    changes: list[dict[str, Any]],
    changeset_path: Path | None = None,
) -> ShadowManifest:
    template = shadow_cfg.get("collection_name_template", "{collection}__shadow__{ts}")
    shadow_name = render_shadow_name(template, baseline_collection)
    shadow_configset = f"{shadow_name}__cfg"
    warnings: list[str] = []
    configset_isolated = True
    baseline_configset_hash: str | None = None
    shadow_configset_hash: str | None = None
    configset_patch: dict[str, Any] = {}

    baseline_configset = collection_config_name(client, baseline_collection)
    if has_configset_updates(changes):
        try:
            with tempfile.TemporaryDirectory(prefix="solrguard-configset-") as tmp:
                workspace = Path(tmp)
                configset_root = _materialize_baseline_configset(
                    client=client,
                    baseline_configset=baseline_configset,
                    shadow_cfg=shadow_cfg,
                    workspace=workspace,
                    changeset_path=changeset_path,
                )
                baseline_configset_hash = hash_directory(configset_root)
                configset_patch = apply_configset_updates(
                    configset_dir=configset_root,
                    changes=changes,
                    changeset_path=changeset_path,
                )
                shadow_configset_hash = hash_directory(configset_root)
                upload_configset_from_dir(
                    client=client,
                    name=shadow_configset,
                    configset_dir=configset_root,
                    overwrite=True,
                    cleanup=True,
                )
                if bool(shadow_cfg.get("promote_uploaded_configset_trusted", True)):
                    promoted_name = f"{shadow_configset}__trusted"
                    try:
                        create_configset(
                            client,
                            promoted_name,
                            shadow_configset,
                            configset_props={"trusted": "true"},
                        )
                        try:
                            delete_configset(client, shadow_configset)
                        except SolrRequestError:
                            pass
                        shadow_configset = promoted_name
                    except SolrRequestError as exc:
                        warnings.append(
                            "Unable to promote uploaded configset to trusted; proceeding with "
                            f"uploaded configset {shadow_configset}. Reason: {exc}"
                        )
        except Exception as exc:  # noqa: BLE001
            allow_fallback = bool(shadow_cfg.get("allow_shared_configset_fallback", False))
            if not allow_fallback:
                raise
            warnings.append(
                "Configset patch workflow failed; falling back to unpatched configset mode. "
                f"Reason: {exc}"
            )
            configset_patch = {
                "applied": [],
                "skipped": True,
                "error": str(exc),
            }
            try:
                create_configset(client, shadow_configset, baseline_configset)
            except SolrRequestError:
                shadow_configset = baseline_configset
                configset_isolated = False
    else:
        try:
            create_configset(client, shadow_configset, baseline_configset)
        except SolrRequestError:
            allow_fallback = bool(shadow_cfg.get("allow_shared_configset_fallback", False))
            if not allow_fallback:
                raise
            warning = (
                "Falling back to shared configset because isolated clone was rejected by Solr; "
                "baseline config may be affected. Enable auth or provide untrusted base configset "
                "to avoid this mode."
            )
            warnings.append(warning)
            shadow_configset = baseline_configset
            configset_isolated = False

    create_collection(
        client,
        name=shadow_name,
        num_shards=int(shadow_cfg.get("num_shards", 1)),
        replication_factor=int(shadow_cfg.get("replication_factor", 1)),
        config_name=shadow_configset,
    )

    applied = apply_schema_operations(client, shadow_name, baseline_schema, changes)

    return ShadowManifest(
        shadow_collection=shadow_name,
        shadow_solr_url=shadow_solr_url,
        created_at=utc_now_iso(),
        applied_changes=applied,
        baseline_collection=baseline_collection,
        baseline_solr_url=baseline_solr_url,
        shadow_configset=shadow_configset,
        baseline_configset=baseline_configset,
        baseline_configset_hash=baseline_configset_hash,
        shadow_configset_hash=shadow_configset_hash,
        configset_isolated=configset_isolated,
        configset_patch=configset_patch,
        warnings=warnings,
    )


def cleanup_shadow(
    client: Any,
    shadow_collection: str,
    shadow_configset: str | None = None,
) -> dict[str, Any]:
    result = {"collection": delete_collection(client, shadow_collection)}
    if shadow_configset:
        result["configset"] = delete_configset(client, shadow_configset)
    return result
