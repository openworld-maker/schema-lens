"""Shadow collection lifecycle manager."""

from __future__ import annotations

from typing import Any

from schema_lens.changesets.apply_schema import apply_schema_operations
from schema_lens.errors import SolrRequestError
from schema_lens.shadow.manifest import ShadowManifest
from schema_lens.shadow.naming import render_shadow_name
from schema_lens.solr.collections_api import (
    collection_config_name,
    create_collection,
    delete_collection,
)
from schema_lens.solr.configsets_api import create_configset, delete_configset
from schema_lens.util.time import utc_now_iso


def create_shadow(
    *,
    client: Any,
    baseline_collection: str,
    baseline_solr_url: str,
    shadow_solr_url: str,
    shadow_cfg: dict[str, Any],
    baseline_schema: dict[str, Any],
    changes: list[dict[str, Any]],
) -> ShadowManifest:
    template = shadow_cfg.get("collection_name_template", "{collection}__shadow__{ts}")
    shadow_name = render_shadow_name(template, baseline_collection)
    shadow_configset = f"{shadow_name}__cfg"
    warnings: list[str] = []
    configset_isolated = True

    baseline_configset = collection_config_name(client, baseline_collection)
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
        configset_isolated=configset_isolated,
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
