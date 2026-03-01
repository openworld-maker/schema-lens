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
from schema_lens.config import RunManifest
from schema_lens.data.docs_loader import load_docs
from schema_lens.errors import StageError
from schema_lens.http.client import SolrHttpClient
from schema_lens.logging import configure_logging
from schema_lens.queries.loader import load_queries
from schema_lens.replay.runner import run_replay
from schema_lens.report.html_report import render_html_report
from schema_lens.report.json_report import build_report_json
from schema_lens.shadow.manager import cleanup_shadow, create_shadow
from schema_lens.solr.admin_api import system_info
from schema_lens.solr.collections_api import cluster_status
from schema_lens.solr.schema_api import get_schema
from schema_lens.solr.update_api import post_docs
from schema_lens.util.io import ensure_dir, read_json, write_json, write_text
from schema_lens.util.time import utc_now_iso

app = typer.Typer(help="Schema Lens: Solr schema evolution impact simulator")
shadow_app = typer.Typer(help="Shadow collection operations")
app.add_typer(shadow_app, name="shadow")


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
            "shadow_json": str((out / "shadow.json").resolve()),
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

    docs_path = _resolve_path(changeset_path, docs_source["path"])
    queries_path = _resolve_path(changeset_path, queries_source["path"])

    manifest.inputs.update(
        {
            "docs_path": str(docs_path),
            "queries_path": str(queries_path),
        }
    )

    baseline_client = SolrHttpClient(baseline_url, verbose=verbose)
    shadow_client = SolrHttpClient(shadow_url, verbose=verbose)
    run_started = perf_counter()

    shadow_name: str | None = None
    replay_data: dict[str, Any] = {}
    compare_data: dict[str, Any] = {}

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

        with stage("index"):
            docs = load_docs(
                docs_path,
                fmt=docs_source.get("format"),
                id_field=docs_source.get("id_field", "id"),
                sample_n=data_cfg.get("sample_n"),
            )
            if not shadow_name:
                raise StageError("Shadow name unavailable during indexing stage")
            indexed = _index_in_batches(shadow_client, shadow_name, docs, batch_size=batch_size)
            manifest.stats["docs_indexed"] = indexed

            shadow_json_path = Path(manifest.outputs["shadow_json"])
            existing_shadow_manifest = read_json(shadow_json_path)
            existing_shadow_manifest["docs_indexed"] = indexed
            write_json(shadow_json_path, existing_shadow_manifest)

        with stage("replay"):
            query_cases = load_queries(
                queries_path,
                fmt=queries_source.get("format", "simple"),
                max_queries=query_cfg.get("max_queries"),
            )
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
