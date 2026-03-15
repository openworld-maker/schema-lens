"""Run compare across two live environments."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import yaml

from schema_lens.env_compare.diff import build_environment_compare
from schema_lens.env_compare.models import EnvironmentConfig
from schema_lens.http.client import SolrHttpClient
from schema_lens.queries.loader import load_queries
from schema_lens.replay.runner import run_replay


def load_env_config(path: Path) -> EnvironmentConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Environment config must be an object: {path}")
    return EnvironmentConfig(
        name=str(payload.get("name") or path.stem),
        solr_url=str(payload.get("solr_url")),
        collection=str(payload.get("collection")),
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
    auth_type = str(env.auth.get("type", "none")).lower()
    if auth_type == "basic":
        raw = f"{env.auth.get('username', '')}:{env.auth.get('password', '')}"
        token = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    elif auth_type == "bearer":
        headers["Authorization"] = f"Bearer {env.auth.get('token', '')}"
    return SolrHttpClient(env.solr_url, headers=headers, verbose=verbose)


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

    replay["baseline"] = env1.to_dict()
    replay["shadow"] = env2.to_dict()
    compare = build_environment_compare(replay, k, env1.to_dict(), env2.to_dict())
    compare["environment_compare"]["replay_stats"] = replay.get("stats", {})
    return {"replay": replay, "compare": compare}
