"""Typer CLI for schema-lens."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

import typer

from schema_lens.changesets.apply_queryparams import merge_queryparams
from schema_lens.changesets.parser import parse_changeset
from schema_lens.changesets.validator import validate_changeset
from schema_lens.compare.diff import compare_replay
from schema_lens.compare.explain_fetcher import fetch_explains
from schema_lens.compare.gate import evaluate_gate, load_gate_policy
from schema_lens.config import RunManifest
from schema_lens.data.docs_loader import load_docs
from schema_lens.data.solr_sampler import sample_docs_from_solr
from schema_lens.errors import StageError
from schema_lens.http.client import SolrHttpClient
from schema_lens.logging import configure_logging
from schema_lens.queries.loader import load_queries
from schema_lens.queries.sampler import sample_queries
from schema_lens.queries.sanitize import sanitize_params
from schema_lens.queries.sources.solr_request_log import extract_queries_from_log
from schema_lens.replay.runner import run_replay
from schema_lens.report.html_report import render_html_report
from schema_lens.report.json_report import build_report_json
from schema_lens.schema.preflight import run_preflight
from schema_lens.shadow.manager import cleanup_shadow, create_shadow
from schema_lens.solr.admin_api import system_info
from schema_lens.solr.collections_api import cluster_status
from schema_lens.solr.schema_api import get_schema
from schema_lens.solr.update_api import post_docs
from schema_lens.util.io import ensure_dir, read_json, write_json, write_jsonl, write_text
from schema_lens.util.time import utc_now_iso

app = typer.Typer(help="Schema Lens: Solr schema evolution impact simulator")
shadow_app = typer.Typer(help="Shadow collection operations")
queries_app = typer.Typer(help="Query source operations")
docs_app = typer.Typer(help="Document source operations")
app.add_typer(shadow_app, name="shadow")
app.add_typer(queries_app, name="queries")
app.add_typer(docs_app, name="docs")


def _hash_obj(data: Any) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _resolve_path(base_file: Path, maybe_rel: str) -> Path:
    path = Path(maybe_rel)
    if path.is_absolute():
        return path
    from_changeset = (base_file.parent / path).resolve()
    if from_changeset.exists():
        return from_changeset
    from_cwd = (Path.cwd() / path).resolve()
    if from_cwd.exists():
        return from_cwd
    return from_changeset


def _inspect_collection(solr_url: str, collection: str, verbose: bool = False) -> dict[str, Any]:
    client = SolrHttpClient(solr_url, verbose=verbose)
    try:
        schema = get_schema(client, collection)
        sysinfo = system_info(client)
        cluster = None
        try:
            cluster = cluster_status(client, collection)
        except Exception:  # noqa: BLE001
            cluster = {"warning": "Cluster status unavailable (standalone or unsupported mode)"}

        return {
            "solr_url": solr_url,
            "collection": collection,
            "schema": schema,
            "system_info": sysinfo,
            "cluster_status": cluster,
        }
    finally:
        client.close()


def _index_in_batches(
    client: SolrHttpClient,
    collection: str,
    docs: list[dict[str, Any]],
    batch_size: int,
) -> int:
    indexed = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        post_docs(client, collection, batch)
        indexed += len(batch)
    return indexed


def _load_and_validate_changeset(changeset_path: Path, check_paths: bool = True):
    changeset = parse_changeset(changeset_path)
    report = validate_changeset(changeset, check_paths=check_paths)
    if report.errors:
        for err in report.errors:
            typer.echo(f"ERROR: {err}")
        raise typer.Exit(code=1)
    for warning in report.warnings:
        typer.echo(f"WARNING: {warning}")
    return changeset


@app.command()
def validate(
    changeset_path: Path = typer.Argument(..., exists=True, readable=True),
    check_solr: bool = typer.Option(True, "--check-solr/--no-check-solr"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Validate a changeset file."""
    configure_logging(verbose)
    changeset = _load_and_validate_changeset(changeset_path, check_paths=True)

    if check_solr:
        baseline = changeset.baseline
        client = SolrHttpClient(baseline["solr_url"], verbose=verbose)
        try:
            get_schema(client, baseline["collection"])
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"ERROR: Solr endpoint validation failed: {exc}")
            raise typer.Exit(code=1) from exc
        finally:
            client.close()

    typer.echo("OK")


@app.command()
def inspect(
    solr_url: str = typer.Option(..., "--solr-url"),
    collection: str = typer.Option(..., "--collection"),
    out: Path = typer.Option(..., "--out"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Inspect schema/system metadata for a collection."""
    configure_logging(verbose)
    payload = _inspect_collection(solr_url, collection, verbose=verbose)
    write_json(out, payload)
    typer.echo(str(out))


@shadow_app.command("create")
def shadow_create(
    changeset_path: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Create and configure shadow collection."""
    configure_logging(verbose)
    changeset = _load_and_validate_changeset(changeset_path, check_paths=False)

    baseline = changeset.baseline
    shadow_cfg = changeset.shadow

    baseline_url = baseline["solr_url"]
    baseline_collection = baseline["collection"]
    shadow_url = shadow_cfg.get("solr_url", baseline_url)

    baseline_client = SolrHttpClient(baseline_url, verbose=verbose)
    shadow_client = SolrHttpClient(shadow_url, verbose=verbose)
    try:
        baseline_schema = get_schema(baseline_client, baseline_collection)
        manifest = create_shadow(
            client=shadow_client,
            baseline_collection=baseline_collection,
            baseline_solr_url=baseline_url,
            shadow_solr_url=shadow_url,
            shadow_cfg=shadow_cfg,
            baseline_schema=baseline_schema,
            changes=changeset.changes,
        )
        write_json(out, manifest.to_dict())
    finally:
        baseline_client.close()
        shadow_client.close()

    typer.echo(str(out))


@shadow_app.command("index")
def shadow_index(
    shadow: Path = typer.Option(..., "--shadow", exists=True, readable=True),
    docs: Path = typer.Option(..., "--docs", exists=True, readable=True),
    batch_size: int = typer.Option(100, "--batch-size"),
    format: str = typer.Option("jsonl", "--format"),
    id_field: str = typer.Option("id", "--id-field"),
    sample_n: int | None = typer.Option(None, "--sample-n"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Index docs into a shadow collection using a shadow manifest."""
    configure_logging(verbose)
    manifest = read_json(shadow)
    docs_payload = load_docs(docs, fmt=format, id_field=id_field, sample_n=sample_n)

    client = SolrHttpClient(manifest["shadow_solr_url"], verbose=verbose)
    try:
        indexed = _index_in_batches(client, manifest["shadow_collection"], docs_payload, batch_size)
    finally:
        client.close()

    manifest["docs_indexed"] = indexed
    write_json(shadow, manifest)
    typer.echo(f"Indexed {indexed} docs")


@queries_app.command("extract")
def queries_extract(
    from_path: Path = typer.Option(..., "--from", exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    max_queries: int | None = typer.Option(None, "--max"),
    sample: str = typer.Option("reservoir", "--sample"),
    seed: int | None = typer.Option(None, "--seed"),
    sanitize: bool = typer.Option(True, "--sanitize/--no-sanitize"),
    format: str = typer.Option("solr_params", "--format"),
) -> None:
    """Extract canonical replay queries from request logs."""
    rows = extract_queries_from_log(from_path, fmt=format)
    sanitized_rows = []
    for row in rows:
        params = row.get("params", {})
        if isinstance(params, dict):
            row = dict(row)
            row["params"] = sanitize_params(params, enabled=sanitize)
            sanitized_rows.append(row)

    sampled = sample_queries(
        sanitized_rows,
        mode=sample,
        max_queries=max_queries,
        seed=seed,
    )
    write_jsonl(out, sampled)
    typer.echo(str(out))


@docs_app.command("sample")
def docs_sample(
    solr_url: str = typer.Option(..., "--solr-url"),
    collection: str = typer.Option(..., "--collection"),
    mode: str = typer.Option("cursormark", "--mode"),
    query: str = typer.Option("*:*", "--query"),
    fl: str = typer.Option("*", "--fl"),
    sort: str = typer.Option("id asc", "--sort"),
    sample_n: int = typer.Option(50000, "--sample-n"),
    batch_size: int = typer.Option(500, "--batch-size"),
    out: Path = typer.Option(..., "--out"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Sample documents from Solr and persist as JSONL."""
    configure_logging(verbose)
    client = SolrHttpClient(solr_url, verbose=verbose)
    try:
        docs, used_mode = sample_docs_from_solr(
            client=client,
            collection=collection,
            mode=mode,
            query=query,
            fl=fl,
            sort=sort,
            sample_n=sample_n,
            batch_size=batch_size,
        )
    finally:
        client.close()

    write_jsonl(out, docs)
    typer.echo(f"{out} ({len(docs)} docs, mode={used_mode})")


@app.command()
def replay(
    baseline_solr_url: str = typer.Option(..., "--baseline-solr-url"),
    baseline_collection: str = typer.Option(..., "--baseline-collection"),
    shadow_solr_url: str = typer.Option(..., "--shadow-solr-url"),
    shadow_collection: str = typer.Option(..., "--shadow-collection"),
    queries: Path = typer.Option(..., "--queries", exists=True, readable=True),
    k: int = typer.Option(10, "--k"),
    out: Path = typer.Option(..., "--out"),
    query_format: str = typer.Option("simple", "--query-format"),
    max_queries: int | None = typer.Option(None, "--max-queries"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Replay queries against baseline and shadow collections."""
    configure_logging(verbose)
    query_cases = load_queries(queries, fmt=query_format, max_queries=max_queries)

    baseline_client = SolrHttpClient(baseline_solr_url, verbose=verbose)
    shadow_client = SolrHttpClient(shadow_solr_url, verbose=verbose)
    try:
        replay_data = run_replay(
            baseline_client=baseline_client,
            baseline_collection=baseline_collection,
            shadow_client=shadow_client,
            shadow_collection=shadow_collection,
            queries=query_cases,
            request_defaults={},
            k=k,
        )
    finally:
        baseline_client.close()
        shadow_client.close()

    replay_data["baseline"] = {
        "solr_url": baseline_solr_url,
        "collection": baseline_collection,
    }
    replay_data["shadow"] = {
        "solr_url": shadow_solr_url,
        "collection": shadow_collection,
    }
    write_json(out, replay_data)
    typer.echo(str(out))


@app.command()
def compare(
    replay: Path = typer.Option(..., "--replay", exists=True, readable=True),
    k: int = typer.Option(10, "--k"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Compare replay outputs and compute metrics."""
    replay_data = read_json(replay)
    compare_data = compare_replay(replay_data, k=k)
    write_json(out, compare_data)
    typer.echo(str(out))


@app.command()
def gate(
    compare: Path = typer.Option(..., "--compare", exists=True, readable=True),
    policy: Path = typer.Option(..., "--policy", exists=True, readable=True),
) -> None:
    """Evaluate a relevance quality gate policy against compare output."""
    try:
        compare_data = read_json(compare)
        policy_data = load_gate_policy(policy)
        result = evaluate_gate(
            compare_data=compare_data,
            policy_data=policy_data,
            policy_dir=policy.parent.resolve(),
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Gate evaluation failed: {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(result, indent=2))
    if not result.get("pass", False):
        raise typer.Exit(code=2)


@app.command()
def report(
    compare: Path = typer.Option(..., "--compare", exists=True, readable=True),
    manifest: Path = typer.Option(..., "--manifest", exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    replay: Path | None = typer.Option(None, "--replay"),
) -> None:
    """Generate JSON and HTML reports."""
    compare_data = read_json(compare)
    manifest_data = read_json(manifest)

    replay_data: dict[str, Any] = {"stats": {"failures": 0}}
    if replay:
        replay_data = read_json(replay)
    else:
        replay_path = manifest_data.get("outputs", {}).get("replay_json")
        if replay_path:
            rp = Path(replay_path)
            if rp.exists():
                replay_data = read_json(rp)

    report_data = build_report_json(
        manifest=manifest_data,
        compare_data=compare_data,
        replay_data=replay_data,
    )

    ensure_dir(out)
    report_json_path = out / "report.json"
    report_html_path = out / "report.html"
    write_json(report_json_path, report_data)

    template_dir = Path(__file__).parent / "report" / "templates"
    html = render_html_report(report_data, template_dir)
    write_text(report_html_path, html)

    typer.echo(str(report_json_path))
    typer.echo(str(report_html_path))


@app.command()
def run(
    changeset_path: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    k: int | None = typer.Option(None, "--k"),
    cleanup: bool | None = typer.Option(None, "--cleanup/--no-cleanup"),
    batch_size: int = typer.Option(100, "--batch-size"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Run full end-to-end schema lens workflow."""
    configure_logging(verbose)
    changeset = _load_and_validate_changeset(changeset_path, check_paths=True)

    ensure_dir(out)

    run_id = str(uuid.uuid4())
    started = utc_now_iso()
    manifest = RunManifest(
        run_id=run_id,
        started_at=started,
        inputs={
            "changeset_path": str(changeset_path.resolve()),
        },
        outputs={
            "out_dir": str(out.resolve()),
            "run_manifest": str((out / "run_manifest.json").resolve()),
            "inspect_json": str((out / "inspect.json").resolve()),
            "schema_risk_json": str((out / "schema_risk.json").resolve()),
            "shadow_json": str((out / "shadow.json").resolve()),
            "docs_sample_jsonl": str((out / "docs_sample.jsonl").resolve()),
            "queries_extracted_jsonl": str((out / "queries_extracted.jsonl").resolve()),
            "replay_json": str((out / "replay.json").resolve()),
            "compare_json": str((out / "compare.json").resolve()),
            "report_json": str((out / "report.json").resolve()),
            "report_html": str((out / "report.html").resolve()),
        },
        settings={},
        stats={"docs_indexed": 0, "queries_run": 0, "failures": 0},
        stages={},
    )

    baseline_cfg = changeset.baseline
    shadow_cfg = changeset.shadow
    data_cfg = changeset.data
    query_cfg = changeset.queries
    eval_cfg = changeset.evaluation

    baseline_url = baseline_cfg["solr_url"]
    baseline_collection = baseline_cfg["collection"]
    shadow_url = shadow_cfg.get("solr_url", baseline_url)

    effective_k = int(k if k is not None else eval_cfg.get("k", 10))
    effective_cleanup = (
        cleanup if cleanup is not None else bool(shadow_cfg.get("cleanup", True))
    )

    manifest.settings.update(
        {
            "k": effective_k,
            "cleanup": effective_cleanup,
            "sample_n": data_cfg.get("sample_n"),
            "max_queries": query_cfg.get("max_queries"),
        }
    )

    docs_source = data_cfg.get("docs_source", {})
    queries_source = query_cfg.get("source", {})
    docs_source_type = str(docs_source.get("type", "file"))
    query_source_type = str(queries_source.get("type", "file"))

    manifest.inputs.update(
        {
            "doc_source_type": docs_source_type,
            "query_source_type": query_source_type,
        }
    )

    docs_path: Path | None = None
    if docs_source_type == "file":
        docs_path = _resolve_path(changeset_path, docs_source["path"])

    queries_path = _resolve_path(changeset_path, queries_source["path"])
    manifest.inputs.update(
        {
            "queries_path": str(queries_path),
        }
    )
    if docs_path:
        manifest.inputs["docs_path"] = str(docs_path)

    baseline_client = SolrHttpClient(baseline_url, verbose=verbose)
    shadow_client = SolrHttpClient(shadow_url, verbose=verbose)
    run_started = perf_counter()

    shadow_name: str | None = None
    replay_data: dict[str, Any] = {}
    compare_data: dict[str, Any] = {}
    schema_risk_data: dict[str, Any] = {}
    docs_payload: list[dict[str, Any]] = []
    query_cases = []

    def stage(name: str):
        class StageCtx:
            def __enter__(self_inner):
                manifest.stages[name] = {"started_at": utc_now_iso(), "status": "running"}
                self_inner.started = perf_counter()
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                elapsed = perf_counter() - self_inner.started
                manifest.stages[name]["duration_seconds"] = round(elapsed, 3)
                if exc:
                    manifest.stages[name]["status"] = "failed"
                    manifest.stages[name]["error"] = str(exc)
                else:
                    manifest.stages[name]["status"] = "ok"
                return False

        return StageCtx()

    try:
        with stage("inspect"):
            inspect_payload = _inspect_collection(
                baseline_url,
                baseline_collection,
                verbose=verbose,
            )
            write_json(Path(manifest.outputs["inspect_json"]), inspect_payload)
            baseline_schema = inspect_payload.get("schema", {})
            manifest.baseline = {
                "solr_url": baseline_url,
                "collection": baseline_collection,
                "schema_hash": _hash_obj(baseline_schema),
                "system_info": inspect_payload.get("system_info", {}),
            }

        with stage("preflight"):
            preflight_cfg = changeset.raw.get("preflight", {})
            fail_on_risk = bool(preflight_cfg.get("fail_on_risk", False))
            schema_risk_data = run_preflight(
                baseline_schema,
                changeset.changes,
                fail_on_risk=fail_on_risk,
            )
            write_json(Path(manifest.outputs["schema_risk_json"]), schema_risk_data)
            manifest.settings["preflight"] = {
                "fail_on_risk": fail_on_risk,
                "summary": schema_risk_data.get("summary", {}),
            }
            if schema_risk_data.get("block_run"):
                raise StageError("preflight blocked run due to HIGH schema risks")

        with stage("shadow_create"):
            shadow_manifest = create_shadow(
                client=shadow_client,
                baseline_collection=baseline_collection,
                baseline_solr_url=baseline_url,
                shadow_solr_url=shadow_url,
                shadow_cfg=shadow_cfg,
                baseline_schema=baseline_schema,
                changes=changeset.changes,
            )
            shadow_name = shadow_manifest.shadow_collection
            write_json(Path(manifest.outputs["shadow_json"]), shadow_manifest.to_dict())
            manifest.shadow = {
                "solr_url": shadow_url,
                "collection": shadow_name,
                "created": True,
                "config_used_hash": _hash_obj(changeset.raw),
                "applied_changes": shadow_manifest.applied_changes,
                "shadow_configset": shadow_manifest.shadow_configset,
                "baseline_configset": shadow_manifest.baseline_configset,
                "configset_isolated": shadow_manifest.configset_isolated,
                "warnings": shadow_manifest.warnings,
            }

        with stage("docs_sample_or_load"):
            if docs_source_type == "file":
                if docs_path is None:
                    raise StageError("docs path unavailable for file source")
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
                source_query = str(docs_source.get("query", "*:*"))
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
                    sample_path = Path(manifest.outputs["docs_sample_jsonl"])

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

                write_jsonl(sample_path, docs_payload)
                manifest.inputs["docs_sample_path"] = str(sample_path.resolve())
                manifest.settings["doc_sampling"] = {
                    "solr_url": source_url,
                    "collection": source_collection,
                    "mode_requested": source_mode,
                    "mode_used": used_mode,
                    "query": source_query,
                    "fl": source_fl,
                    "sort": source_sort,
                    "sample_n": source_sample_n,
                    "batch_size": source_batch_size,
                }

        with stage("index"):
            if not shadow_name:
                raise StageError("Shadow name unavailable during indexing stage")
            indexed = _index_in_batches(
                shadow_client,
                shadow_name,
                docs_payload,
                batch_size=batch_size,
            )
            manifest.stats["docs_indexed"] = indexed

            shadow_json_path = Path(manifest.outputs["shadow_json"])
            existing_shadow_manifest = read_json(shadow_json_path)
            existing_shadow_manifest["docs_indexed"] = indexed
            write_json(shadow_json_path, existing_shadow_manifest)

        with stage("queries_extract_or_load"):
            if query_source_type == "file":
                query_cases = load_queries(
                    queries_path,
                    fmt=queries_source.get("format", "simple"),
                    max_queries=query_cfg.get("max_queries"),
                )
            else:
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
                extracted_path = Path(manifest.outputs["queries_extracted_jsonl"])
                write_jsonl(extracted_path, sampled_rows)
                manifest.inputs["queries_extracted_path"] = str(extracted_path.resolve())
                manifest.settings["query_sampling"] = {
                    "mode": sampling_mode,
                    "seed": sampling_seed,
                    "sanitize_enabled": sanitize_enabled,
                }
                query_cases = load_queries(extracted_path, fmt="jsonl")

        with stage("replay"):
            if not shadow_name:
                raise StageError("Shadow name unavailable during replay stage")
            request_defaults = baseline_cfg.get("request_defaults", {})
            merged_defaults = merge_queryparams(request_defaults, changeset.changes)
            replay_data = run_replay(
                baseline_client=baseline_client,
                baseline_collection=baseline_collection,
                shadow_client=shadow_client,
                shadow_collection=shadow_name,
                queries=query_cases,
                request_defaults=merged_defaults,
                k=effective_k,
            )
            replay_data["baseline"] = {
                "solr_url": baseline_url,
                "collection": baseline_collection,
            }
            replay_data["shadow"] = {
                "solr_url": shadow_url,
                "collection": shadow_name,
            }
            write_json(Path(manifest.outputs["replay_json"]), replay_data)
            manifest.stats["queries_run"] = len(query_cases)
            manifest.stats["failures"] = replay_data.get("stats", {}).get("failures", 0)

        with stage("compare"):
            compare_data = compare_replay(replay_data, effective_k)
            compare_data["schema_safety_findings"] = schema_risk_data
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

        with stage("explain"):
            explain_cfg = eval_cfg.get("explain", {})
            if explain_cfg.get("enabled", False):
                bundles = fetch_explains(
                    baseline_client=baseline_client,
                    baseline_collection=baseline_collection,
                    shadow_client=shadow_client,
                    shadow_collection=shadow_name,
                    replay_pairs=replay_data.get("pairs", []),
                    diffs=compare_data.get("diffs", []),
                    k=effective_k,
                    max_queries=int(explain_cfg.get("max_queries", 25)),
                    max_docs_per_query=int(explain_cfg.get("max_docs_per_query", 3)),
                    structured=bool(explain_cfg.get("structured", False)),
                )
                compare_data["explain_bundles"] = bundles
                write_json(Path(manifest.outputs["compare_json"]), compare_data)
            else:
                compare_data["explain_bundles"] = []

        with stage("report"):
            report_data = build_report_json(
                manifest=manifest.to_dict(),
                compare_data=compare_data,
                replay_data=replay_data,
            )
            write_json(Path(manifest.outputs["report_json"]), report_data)
            template_dir = Path(__file__).parent / "report" / "templates"
            html = render_html_report(report_data, template_dir)
            write_text(Path(manifest.outputs["report_html"]), html)

    except Exception as exc:  # noqa: BLE001
        raise StageError(f"run failed: {exc}") from exc

    finally:
        with stage("cleanup"):
            if effective_cleanup and shadow_name:
                try:
                    cleanup_shadow(
                        shadow_client,
                        shadow_name,
                        manifest.shadow.get("shadow_configset")
                        if manifest.shadow.get("configset_isolated")
                        else None,
                    )
                    manifest.shadow["cleanup_deleted"] = True
                except Exception as exc:  # noqa: BLE001
                    manifest.shadow["cleanup_deleted"] = False
                    manifest.shadow["cleanup_error"] = str(exc)
            elif shadow_name:
                manifest.shadow["cleanup_deleted"] = False
                manifest.shadow["cleanup_skipped"] = True

        manifest.ended_at = utc_now_iso()
        manifest.stats["duration_seconds"] = round(
            perf_counter() - run_started, 3
        )
        write_json(Path(manifest.outputs["run_manifest"]), manifest.to_dict())
        baseline_client.close()
        shadow_client.close()

    typer.echo(str(Path(manifest.outputs["report_json"])))
    typer.echo(str(Path(manifest.outputs["report_html"])))


@app.callback()
def main() -> None:
    """Schema Lens command group."""
    return None


if __name__ == "__main__":
    app()
