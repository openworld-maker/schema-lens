from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schema_lens.compat import (
    capabilities_for_version,
    compatibility_contract,
    detect_solr_version,
    detect_version_info,
    probe_runtime_capabilities,
)
from schema_lens.compat.adapters import (
    configset_download_supported,
    configset_upload_supported,
    metrics_supported,
    structured_explain_supported,
    vector_supported,
)
from schema_lens.snapshot.snapshotter import capture_snapshot, load_snapshot
from schema_lens.util.io import write_json, write_text


@dataclass
class SnapshotCompatRuntime:
    baseline_schema: dict[str, Any]
    inspect_payload: dict[str, Any]
    compat_version: str | None
    compat_caps: dict[str, Any]
    compat_payload: dict[str, Any]
    snapshot_hash: str


def run_snapshot_and_compat(
    *,
    snapshot_path: Path | None,
    baseline_url: str,
    baseline_collection: str,
    out_dir: Path,
    request_defaults: dict[str, Any],
    verbose: bool,
    outputs: dict[str, str],
    manifest_inputs: dict[str, Any],
    baseline_client: Any | None = None,
) -> SnapshotCompatRuntime:
    if snapshot_path:
        snapshot_data = load_snapshot(snapshot_path.resolve())
        snapshot_manifest = snapshot_data.get("manifest", {})
        baseline_schema = snapshot_data.get("schema", {})
        system = snapshot_data.get("system", {})
        collection_state = snapshot_data.get("collection_state", {})
        snapshot_hash = str(snapshot_data.get("hash"))
        inspect_payload = {
            "solr_url": baseline_url,
            "collection": baseline_collection,
            "schema": baseline_schema,
            "system_info": system,
            "cluster_status": collection_state,
            "snapshot_manifest": snapshot_manifest,
        }

        write_json(Path(outputs["snapshot_json"]), snapshot_manifest)
        write_json(Path(outputs["snapshot_schema_json"]), baseline_schema)
        write_json(Path(outputs["snapshot_system_json"]), system)
        write_json(Path(outputs["snapshot_collection_json"]), collection_state)
        write_text(Path(outputs["snapshot_hash_txt"]), snapshot_hash + "\n")
        manifest_inputs["snapshot_path"] = str(snapshot_path.resolve())
    else:
        captured = capture_snapshot(
            solr_url=baseline_url,
            collection=baseline_collection,
            out_dir=out_dir,
            request_defaults=request_defaults,
            verbose=verbose,
        )
        snapshot_manifest = captured["manifest"]
        baseline_schema = captured["schema"]
        system = captured["system"]
        collection_state = captured["collection_state"]
        snapshot_hash = str(snapshot_manifest.get("hash", ""))
        inspect_payload = {
            "solr_url": baseline_url,
            "collection": baseline_collection,
            "schema": baseline_schema,
            "system_info": system,
            "cluster_status": collection_state,
            "snapshot_manifest": snapshot_manifest,
        }
        manifest_inputs["snapshot_path"] = str(out_dir.resolve())

    write_json(Path(outputs["inspect_json"]), inspect_payload)

    compat_version = detect_solr_version(system)
    probe_results: dict[str, bool] | None = None
    if baseline_client is not None:
        probe_results = probe_runtime_capabilities(
            client=baseline_client,
            collection=baseline_collection,
        )

    compat_caps = capabilities_for_version(compat_version, probe_results=probe_results)
    compat_payload = compatibility_contract(
        detect_version_info(system),
        system_info=system,
        probe_results=probe_results,
    )
    compat_payload["degraded_features"] = []
    if not vector_supported(compat_caps):
        compat_payload["degraded_features"].append("vector_hybrid")
    if not structured_explain_supported(compat_caps):
        compat_payload["degraded_features"].append("structured_explain")
    if not metrics_supported(compat_caps):
        compat_payload["degraded_features"].append("metrics_capture")
    if not configset_upload_supported(compat_caps):
        compat_payload["degraded_features"].append("configset_upload")
    if not configset_download_supported(compat_caps):
        compat_payload["degraded_features"].append("configset_download")

    compat_payload.setdefault("warnings", [])
    if probe_results is not None and not probe_results.get("metrics_json", True):
        compat_payload["warnings"].append(
            "Using /admin/mbeans fallback because /admin/metrics JSON was not supported."
        )
    if not vector_supported(compat_caps):
        compat_payload["warnings"].append(
            f"Detected Solr {compat_version or 'unknown'}; vector scenarios disabled because vector capability is not available."
        )

    snapshot_manifest_payload = inspect_payload.get("snapshot_manifest", {})
    if isinstance(snapshot_manifest_payload, dict):
        snapshot_manifest_payload["compatibility"] = compat_payload
        write_json(Path(outputs["snapshot_json"]), snapshot_manifest_payload)

    return SnapshotCompatRuntime(
        baseline_schema=baseline_schema,
        inspect_payload=inspect_payload,
        compat_version=compat_version,
        compat_caps=compat_caps,
        compat_payload=compat_payload,
        snapshot_hash=snapshot_hash,
    )
