"""Run compare across two live environments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from schema_lens.compat import compatibility_contract, detect_version_info, probe_runtime_capabilities
from schema_lens.env_compare.diff import build_environment_compare
from schema_lens.env_compare.models import EnvironmentConfig
from schema_lens.http.client import SolrHttpClient
from schema_lens.queries.loader import load_queries
from schema_lens.replay.runner import run_replay
from schema_lens.security.auth import resolve_auth_material
from schema_lens.security.redaction import redact_headers
from schema_lens.security.redaction import redact_payload
from schema_lens.solr.admin_api import system_info


def load_env_config(path: Path) -> EnvironmentConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Environment config must be an object: {path}")
    return EnvironmentConfig(
        name=str(payload.get("name") or path.stem),
        solr_url=str(payload.get("solr_url")),
        collection=str(payload.get("collection")),
        source_path=str(path.resolve()),
        request_defaults=payload.get("request_defaults", {})
        if isinstance(payload.get("request_defaults"), dict)
        else {},
        auth=payload.get("auth", {}) if isinstance(payload.get("auth"), dict) else {},
        headers={
            str(k): str(v)
            for k, v in (payload.get("headers", {}) or {}).items()
        }
        if isinstance(payload.get("headers"), dict)
        else {},
        notes=str(payload.get("notes")) if payload.get("notes") is not None else None,
    )


def _client_for_env(env: EnvironmentConfig, verbose: bool) -> SolrHttpClient:
    headers = dict(env.headers)
    base_dir = (
        Path(env.source_path).parent
        if isinstance(env.source_path, str) and env.source_path
        else Path.cwd()
    )
    auth = resolve_auth_material(env.auth, base_dir=base_dir)
    headers.update(auth.headers)
    return SolrHttpClient(
        env.solr_url,
        headers=headers,
        cert=auth.cert,
        verify=auth.verify,
        verbose=verbose,
    )


def compare_environments(
    *,
    env1_path: Path,
    env2_path: Path,
    queries_path: Path,
    query_format: str,
    k: int,
    max_queries: int | None,
    verbose: bool,
) -> dict[str, Any]:
    env1 = load_env_config(env1_path)
    env2 = load_env_config(env2_path)
    query_cases = load_queries(queries_path, fmt=query_format, max_queries=max_queries)

    client1 = _client_for_env(env1, verbose)
    client2 = _client_for_env(env2, verbose)
    try:
        env1_system = system_info(client1)
        env2_system = system_info(client2)
        env1_contract = compatibility_contract(
            detect_version_info(env1_system),
            system_info=env1_system,
            probe_results=probe_runtime_capabilities(client=client1, collection=env1.collection),
        )
        env2_contract = compatibility_contract(
            detect_version_info(env2_system),
            system_info=env2_system,
            probe_results=probe_runtime_capabilities(client=client2, collection=env2.collection),
        )
        replay = run_replay(
            baseline_client=client1,
            baseline_collection=env1.collection,
            shadow_client=client2,
            shadow_collection=env2.collection,
            queries=query_cases,
            request_defaults=env1.request_defaults,
            k=k,
        )
    finally:
        client1.close()
        client2.close()

    replay["baseline"] = redact_payload(env1.to_dict())
    replay["shadow"] = redact_payload(env2.to_dict())
    replay["baseline"]["headers"] = redact_headers(env1.headers)
    replay["shadow"]["headers"] = redact_headers(env2.headers)
    compare = build_environment_compare(
        replay,
        k,
        redact_payload(env1.to_dict()),
        redact_payload(env2.to_dict()),
        env1_contract=env1_contract,
        env2_contract=env2_contract,
    )
    compare["environment_compare"]["replay_stats"] = replay.get("stats", {})
    mismatches = (
        compare.get("environment_compare", {})
        .get("compatibility", {})
        .get("capability_mismatches", [])
    )
    compare["compatibility"] = {
        "env1": env1_contract,
        "env2": env2_contract,
        "capability_mismatches": mismatches,
        "warnings": ["Environment capability mismatch detected."] if mismatches else [],
    }
    return {"replay": replay, "compare": compare}
