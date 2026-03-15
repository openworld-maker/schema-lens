from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schema_lens.data.docs_loader import load_docs
from schema_lens.data.solr_sampler import sample_docs_from_solr
from schema_lens.http.client import SolrHttpClient
from schema_lens.queries.loader import load_queries
from schema_lens.queries.model import QueryCase
from schema_lens.queries.normalize import normalize_q, query_fingerprint
from schema_lens.queries.sampler import sample_queries
from schema_lens.queries.sanitize import sanitize_params
from schema_lens.queries.sources.solr_request_log import extract_queries_from_log
from schema_lens.util.io import write_jsonl
from schema_lens.vector.validation import augment_docs_with_embeddings, load_embeddings


def load_or_sample_docs(
    *,
    docs_source_type: str,
    docs_source: dict[str, Any],
    docs_path: Path | None,
    data_cfg: dict[str, Any],
    baseline_url: str,
    baseline_collection: str,
    batch_size: int,
    manifest_inputs: dict[str, Any],
    manifest_settings: dict[str, Any],
    outputs: dict[str, str],
    persist_sensitive_effective: bool,
    privacy_runtime_cfg: dict[str, Any],
    vector_runtime_cfg,
    changeset_path: Path,
    verbose: bool,
) -> list[dict[str, Any]]:
    docs_payload: list[dict[str, Any]]
    if docs_source_type == "file":
        if docs_path is None:
            raise ValueError("docs path unavailable for file source")
        docs_payload = load_docs(
            docs_path,
            fmt=docs_source.get("format"),
            id_field=docs_source.get("id_field", "id"),
            sample_n=data_cfg.get("sample_n"),
        )
    else:
        source_url = str(docs_source.get("solr_url", baseline_url))
        source_collection = str(docs_source.get("collection", baseline_collection))
        source_mode = str(docs_source.get("mode", "cursormark"))
        source_query = str(docs_source.get("query", "*:*") )
        source_fl = str(docs_source.get("fl", "*"))
        source_sort = str(docs_source.get("sort", "id asc"))
        source_sample_n = int(docs_source.get("sample_n", data_cfg.get("sample_n", 50000)))
        source_batch_size = int(docs_source.get("batch_size", batch_size))

        out_sample_path = docs_source.get("out_sample_path")
        if isinstance(out_sample_path, str):
            sample_path = Path(out_sample_path)
            if not sample_path.is_absolute():
                sample_path = (Path.cwd() / sample_path).resolve()
        else:
            sample_path = Path(outputs["docs_sample_jsonl"])

        docs_client = SolrHttpClient(source_url, verbose=verbose)
        try:
            docs_payload, used_mode = sample_docs_from_solr(
                client=docs_client,
                collection=source_collection,
                mode=source_mode,
                query=source_query,
                fl=source_fl,
                sort=source_sort,
                sample_n=source_sample_n,
                batch_size=source_batch_size,
            )
        finally:
            docs_client.close()

        if persist_sensitive_effective and not bool(privacy_runtime_cfg.get("raw_doc_suppression", False)):
            write_jsonl(sample_path, docs_payload)
            manifest_inputs["docs_sample_path"] = str(sample_path.resolve())
        else:
            manifest_inputs["docs_sample_path"] = "<suppressed_by_security_profile>"
        manifest_settings["doc_sampling"] = {
            "solr_url": source_url,
            "collection": source_collection,
            "mode_requested": source_mode,
            "mode_used": used_mode,
            "query": source_query,
            "fl": source_fl,
            "sort": source_sort,
            "sample_n": source_sample_n,
            "batch_size": source_batch_size,
            "persisted_sample": persist_sensitive_effective
            and not bool(privacy_runtime_cfg.get("raw_doc_suppression", False)),
        }

    if vector_runtime_cfg.enabled:
        embedding_source = (
            vector_runtime_cfg.embedding_source
            if isinstance(vector_runtime_cfg.embedding_source, dict)
            else {}
        )
        embedding_map, embedding_source_type = load_embeddings(
            embedding_source=embedding_source,
            changeset_path=changeset_path,
        )
        if embedding_map:
            id_field = str(embedding_source.get("id_field", "id"))
            vector_field = str(
                embedding_source.get("vector_field", vector_runtime_cfg.field)
            )
            embedding_stats = augment_docs_with_embeddings(
                docs=docs_payload,
                embedding_map=embedding_map,
                id_field=id_field,
                vector_field=vector_field,
            )
            manifest_settings["vector_embedding_ingest"] = {
                "source_type": embedding_source_type,
                "path": embedding_source.get("path"),
                "id_field": id_field,
                "vector_field": vector_field,
                "stats": embedding_stats,
            }

    return docs_payload


def load_or_extract_queries(
    *,
    query_source_type: str,
    queries_source: dict[str, Any],
    queries_path: Path,
    query_cfg: dict[str, Any],
    outputs: dict[str, str],
    manifest_inputs: dict[str, Any],
    manifest_settings: dict[str, Any],
    persist_sensitive_effective: bool,
) -> list[QueryCase]:
    if query_source_type == "file":
        return load_queries(
            queries_path,
            fmt=queries_source.get("format", "simple"),
            max_queries=query_cfg.get("max_queries"),
        )

    extracted_rows = extract_queries_from_log(
        queries_path,
        fmt=str(queries_source.get("format", "solr_params")),
    )
    sanitize_cfg = query_cfg.get("sanitize", {})
    if not isinstance(sanitize_cfg, dict):
        sanitize_cfg = {}
    sanitize_enabled = bool(sanitize_cfg.get("enabled", True))
    sanitize_rules = sanitize_cfg.get("rules")

    cleaned_rows = []
    for row in extracted_rows:
        params = row.get("params", {})
        if not isinstance(params, dict):
            continue
        cleaned_rows.append(
            {
                **row,
                "params": sanitize_params(
                    params,
                    enabled=sanitize_enabled,
                    rules=sanitize_rules if isinstance(sanitize_rules, list) else None,
                ),
            }
        )

    sampling_cfg = query_cfg.get("sampling", {})
    if not isinstance(sampling_cfg, dict):
        sampling_cfg = {}
    sampling_mode = str(sampling_cfg.get("mode", "reservoir"))
    sampling_seed = sampling_cfg.get("seed")

    sampled_rows = sample_queries(
        cleaned_rows,
        mode=sampling_mode,
        max_queries=query_cfg.get("max_queries"),
        seed=sampling_seed if isinstance(sampling_seed, int) else None,
    )
    extracted_path = Path(outputs["queries_extracted_jsonl"])
    if persist_sensitive_effective:
        write_jsonl(extracted_path, sampled_rows)
        manifest_inputs["queries_extracted_path"] = str(extracted_path.resolve())
    else:
        manifest_inputs["queries_extracted_path"] = "<suppressed_by_security_profile>"
    manifest_settings["query_sampling"] = {
        "mode": sampling_mode,
        "seed": sampling_seed,
        "sanitize_enabled": sanitize_enabled,
        "persisted_sample": persist_sensitive_effective,
    }
    if persist_sensitive_effective:
        return load_queries(extracted_path, fmt="jsonl")

    query_cases: list[QueryCase] = []
    for idx, row in enumerate(sampled_rows, start=1):
        params = row.get("params", {}) if isinstance(row, dict) else {}
        if not isinstance(params, dict):
            params = {}
        query_cases.append(
            QueryCase(
                id=idx,
                line_no=idx,
                raw_line=json.dumps({"params": params}, sort_keys=True),
                normalized_q=normalize_q(params),
                fingerprint=query_fingerprint(params),
                params=params,
                request_mode="params",
                skip_reasons=[],
                segment={},
            )
        )
    return query_cases
