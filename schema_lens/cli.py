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
from schema_lens.ci.summarize import build_ci_summary_markdown
from schema_lens.compare.diff import compare_replay
from schema_lens.compare.explain_fetcher import fetch_explains
from schema_lens.compare.gate import evaluate_gate, load_gate_policy
from schema_lens.compare.rewrite_diff import load_synonym_rules_from_changes, run_rewrite_diff
from schema_lens.config import RunManifest
from schema_lens.dashboard.app import create_dashboard_app
from schema_lens.data.docs_loader import load_docs
from schema_lens.data.solr_sampler import sample_docs_from_solr
from schema_lens.env_compare.runner import compare_environments
from schema_lens.errors import StageError
from schema_lens.golden.discover import discover_golden_queries
from schema_lens.golden.model import GoldenQuery
from schema_lens.golden.store import append_golden
from schema_lens.http.client import SolrHttpClient
from schema_lens.logging import configure_logging
from schema_lens.ltr.capture import capture_ltr_impact
from schema_lens.monitor.runner import run_monitor
from schema_lens.perf.analyzer import analyze_performance
from schema_lens.perf.solr_metrics import collect_solr_runtime_snapshot
from schema_lens.queries.loader import load_queries
from schema_lens.queries.sampler import sample_queries
from schema_lens.queries.sanitize import sanitize_params
from schema_lens.queries.sources.solr_request_log import extract_queries_from_log
from schema_lens.recommend.engine import build_recommendations
from schema_lens.replay.runner import run_replay
from schema_lens.report.html_report import render_html_report
from schema_lens.report.json_report import build_report_json
from schema_lens.rootcause.engine import analyze_root_causes
from schema_lens.schema.preflight import run_preflight
from schema_lens.shadow.manager import cleanup_shadow, create_shadow
from schema_lens.snapshot.snapshotter import capture_snapshot, load_snapshot
from schema_lens.solr.admin_api import system_info
from schema_lens.solr.collections_api import cluster_status
from schema_lens.solr.schema_api import get_schema
from schema_lens.solr.update_api import post_docs
from schema_lens.util.git import current_git_commit_short
from schema_lens.util.io import ensure_dir, read_json, write_json, write_jsonl, write_text
from schema_lens.util.time import utc_now_iso
from schema_lens.vector.compare import compare_vector_hybrid
from schema_lens.vector.replay import run_vector_scenarios
from schema_lens.vector.scenario_parser import parse_vector_runtime_config
from schema_lens.vector.sensitivity import run_hybrid_sensitivity
from schema_lens.vector.validation import (
    augment_docs_with_embeddings,
    load_embeddings,
    validate_vector_setup,
)

app = typer.Typer(help="Schema Lens: Solr schema evolution impact simulator")
shadow_app = typer.Typer(help="Shadow collection operations")
queries_app = typer.Typer(help="Query source operations")
docs_app = typer.Typer(help="Document source operations")
golden_app = typer.Typer(help="Golden query operations")
ci_app = typer.Typer(help="CI summary operations")
app.add_typer(shadow_app, name="shadow")
app.add_typer(queries_app, name="queries")
app.add_typer(docs_app, name="docs")
app.add_typer(golden_app, name="golden")
app.add_typer(ci_app, name="ci")


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


def _parse_weights(raw: str | None) -> list[float] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    weights: list[float] = []
    for chunk in text.split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            weights.append(float(value))
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid weight value: {value}") from exc
    if not weights:
        return None
    return weights


def _disabled_section(reason: str) -> dict[str, Any]:
    return {"enabled": False, "reason": reason}


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


@app.command()
def snapshot(
    solr_url: str = typer.Option(..., "--solr-url"),
    collection: str = typer.Option(..., "--collection"),
    out: Path = typer.Option(..., "--out"),
    request_defaults: Path | None = typer.Option(None, "--request-defaults"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Capture a reproducible baseline snapshot for a collection."""
    configure_logging(verbose)
    defaults: dict[str, Any] = {}
    if request_defaults:
        loaded = read_json(request_defaults)
        if not isinstance(loaded, dict):
            raise typer.BadParameter("--request-defaults must point to a JSON object")
        defaults = loaded

    captured = capture_snapshot(
        solr_url=solr_url,
        collection=collection,
        out_dir=out,
        request_defaults=defaults,
        verbose=verbose,
    )
    typer.echo(str(captured["paths"]["manifest"]))


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
            changeset_path=changeset_path,
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


@golden_app.command("add")
def golden_add(
    q: str = typer.Option(..., "--q"),
    expect_id: str = typer.Option(..., "--expect-id"),
    out: Path = typer.Option(..., "--out"),
    name: str | None = typer.Option(None, "--name"),
    def_type: str = typer.Option("edismax", "--def-type"),
    must_contain_topk: int = typer.Option(10, "--must-contain-topk"),
) -> None:
    """Append a golden query entry to JSONL."""
    entry = GoldenQuery(
        name=name or q,
        params={"q": q, "defType": def_type},
        expected_ids=[expect_id],
        must_contain_topk=must_contain_topk,
    )
    append_golden(out, entry)
    typer.echo(str(out))


@golden_app.command("discover")
def golden_discover(
    from_path: Path = typer.Option(..., "--from", exists=True, readable=True),
    top: int = typer.Option(50, "--top"),
    out: Path = typer.Option(..., "--out"),
    format: str = typer.Option("jsonl", "--format"),
    default_def_type: str = typer.Option("edismax", "--default-def-type"),
) -> None:
    """Discover top candidate golden queries from query logs/extractions."""
    entries = discover_golden_queries(
        path=from_path,
        top=top,
        fmt=format,
        default_def_type=default_def_type,
    )
    write_jsonl(out, [entry.to_dict() for entry in entries])
    typer.echo(str(out))


@ci_app.command("summarize")
def ci_summarize(
    compare: Path = typer.Option(..., "--compare", exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    policy: Path | None = typer.Option(None, "--policy"),
) -> None:
    """Generate markdown summary for PR checks/comments."""
    compare_data = read_json(compare)
    markdown = build_ci_summary_markdown(
        compare_data,
        compare_path=compare.resolve(),
        policy_path=policy.resolve() if policy else None,
    )
    write_text(out, markdown)
    typer.echo(markdown)


@app.command("recommend")
def recommend(
    run: Path = typer.Option(..., "--run", exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Generate recommendations from a completed run directory."""
    compare_path = run / "compare.json"
    if not compare_path.exists():
        raise typer.BadParameter(f"compare.json not found under {run}")
    compare_data = read_json(compare_path)
    root_causes = compare_data.get("root_causes")
    if not isinstance(root_causes, dict):
        root_causes = analyze_root_causes(
            compare_data=compare_data,
            changes=[],
            baseline_request_defaults={},
        )
    payload = build_recommendations(root_causes)
    write_json(out, payload)
    typer.echo(str(out))


@app.command("compare-env")
def compare_env(
    env1: Path = typer.Option(..., "--env1", exists=True, readable=True),
    env2: Path = typer.Option(..., "--env2", exists=True, readable=True),
    queries: Path = typer.Option(..., "--queries", exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    k: int = typer.Option(10, "--k"),
    query_format: str = typer.Option("jsonl", "--query-format"),
    max_queries: int | None = typer.Option(None, "--max-queries"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Compare two live environments."""
    configure_logging(verbose)
    payload = compare_environments(
        env1_path=env1,
        env2_path=env2,
        queries_path=queries,
        query_format=query_format,
        k=k,
        max_queries=max_queries,
        verbose=verbose,
    )
    ensure_dir(out)
    write_json(out / "replay.json", payload["replay"])
    write_json(out / "compare.json", payload["compare"])
    report_data = build_report_json(
        manifest={
            "inputs": {
                "env1": str(env1.resolve()),
                "env2": str(env2.resolve()),
                "queries_path": str(queries.resolve()),
            },
            "outputs": {
                "compare_json": str((out / "compare.json").resolve()),
                "report_json": str((out / "report.json").resolve()),
                "report_html": str((out / "report.html").resolve()),
                "env_compare_json": str((out / "env_compare.json").resolve()),
            },
        },
        compare_data=payload["compare"],
        replay_data=payload["replay"],
    )
    write_json(out / "env_compare.json", payload["compare"])
    write_json(out / "report.json", report_data)
    template_dir = Path(__file__).parent / "report" / "templates"
    write_text(out / "report.html", render_html_report(report_data, template_dir))
    typer.echo(str((out / "report.json").resolve()))


@app.command("serve")
def serve(
    run: Path | None = typer.Option(None, "--run", exists=True, readable=True),
    compare: Path | None = typer.Option(None, "--compare", exists=True, readable=True),
    port: int = typer.Option(8080, "--port"),
) -> None:
    """Serve a read-only local dashboard for run artifacts."""
    import uvicorn

    if run is None and compare is None:
        raise typer.BadParameter("Provide either --run or --compare")
    if run is not None and compare is not None:
        raise typer.BadParameter("Use only one of --run or --compare")
    source = run if run is not None else compare
    assert source is not None
    base_path = source if source.is_dir() else source.parent
    app_instance = create_dashboard_app(base_path.resolve())
    uvicorn.run(app_instance, host="127.0.0.1", port=port)


@app.command("monitor")
def monitor(
    baseline_snapshot: Path = typer.Option(..., "--baseline-snapshot", exists=True, readable=True),
    queries: Path = typer.Option(..., "--queries", exists=True, readable=True),
    interval: str = typer.Option("24h", "--interval"),
    out: Path = typer.Option(..., "--out"),
    query_format: str = typer.Option("jsonl", "--query-format"),
) -> None:
    """Run one-shot drift monitoring from a prior run/snapshot directory."""
    ensure_dir(out)
    run_monitor(
        baseline_snapshot_dir=baseline_snapshot,
        queries_path=queries,
        query_format=query_format,
        interval=interval,
        out_dir=out,
    )
    typer.echo(str((out / "latest_monitor.json").resolve()))


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
    compare_data.setdefault(
        "performance",
        {"enabled": False, "reason": "Performance capture not enabled."},
    )
    compare_data.setdefault(
        "root_causes",
        {"enabled": False, "reason": "Root-cause analysis not generated."},
    )
    compare_data.setdefault(
        "recommendations",
        {"enabled": False, "reason": "Recommendations not generated."},
    )
    compare_data.setdefault(
        "environment_compare",
        {"enabled": False, "reason": "Environment compare not generated."},
    )
    compare_data.setdefault(
        "ltr_impact",
        {"enabled": False, "reason": "LTR impact not available."},
    )
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
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    k: int | None = typer.Option(None, "--k"),
    cleanup: bool | None = typer.Option(None, "--cleanup/--no-cleanup"),
    batch_size: int = typer.Option(100, "--batch-size"),
    scenario: list[str] | None = typer.Option(None, "--scenario"),
    enable_sensitivity: bool | None = typer.Option(
        None, "--enable-sensitivity/--no-enable-sensitivity"
    ),
    weights: str | None = typer.Option(None, "--weights"),
    vector_dimension_override: int | None = typer.Option(None, "--vector-dimension-override"),
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
            "snapshot_json": str((out / "snapshot.json").resolve()),
            "snapshot_schema_json": str((out / "snapshot.schema.json").resolve()),
            "snapshot_system_json": str((out / "snapshot.system.json").resolve()),
            "snapshot_collection_json": str((out / "snapshot.collection.json").resolve()),
            "snapshot_hash_txt": str((out / "snapshot.hash.txt").resolve()),
            "schema_risk_json": str((out / "schema_risk.json").resolve()),
            "shadow_json": str((out / "shadow.json").resolve()),
            "docs_sample_jsonl": str((out / "docs_sample.jsonl").resolve()),
            "queries_extracted_jsonl": str((out / "queries_extracted.jsonl").resolve()),
            "replay_json": str((out / "replay.json").resolve()),
            "compare_json": str((out / "compare.json").resolve()),
            "vector_validation_json": str((out / "vector_validation.json").resolve()),
            "hybrid_sensitivity_json": str((out / "hybrid_sensitivity.json").resolve()),
            "perf_metrics_json": str((out / "perf_metrics.json").resolve()),
            "rootcauses_json": str((out / "rootcauses.json").resolve()),
            "recommendations_json": str((out / "recommendations.json").resolve()),
            "env_compare_json": str((out / "env_compare.json").resolve()),
            "monitor_history_jsonl": str((out / "monitor_history.jsonl").resolve()),
            "ltr_impact_json": str((out / "ltr_impact.json").resolve()),
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
    selected_scenarios = [item for item in (scenario or []) if item]
    sensitivity_weights = _parse_weights(weights)

    manifest.settings.update(
        {
            "k": effective_k,
            "cleanup": effective_cleanup,
            "sample_n": data_cfg.get("sample_n"),
            "max_queries": query_cfg.get("max_queries"),
            "git_commit": current_git_commit_short(Path.cwd()),
            "vector_cli_overrides": {
                "scenario": selected_scenarios,
                "enable_sensitivity": enable_sensitivity,
                "weights": sensitivity_weights,
                "vector_dimension_override": vector_dimension_override,
            },
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

    vector_runtime_cfg = parse_vector_runtime_config(
        changeset_vector=changeset.vector if hasattr(changeset, "vector") else {},
        evaluation_cfg=eval_cfg,
        default_top_k=effective_k,
        selected_scenarios=selected_scenarios or None,
        sensitivity_enabled_override=enable_sensitivity,
        sensitivity_weights_override=sensitivity_weights,
    )
    manifest.settings["vector"] = vector_runtime_cfg.to_dict()

    baseline_client = SolrHttpClient(baseline_url, verbose=verbose)
    shadow_client = SolrHttpClient(shadow_url, verbose=verbose)
    run_started = perf_counter()

    shadow_name: str | None = None
    replay_data: dict[str, Any] = {}
    compare_data: dict[str, Any] = {}
    schema_risk_data: dict[str, Any] = {}
    vector_validation_data: dict[str, Any] = {"enabled": False}
    vector_replay_data: dict[str, Any] = {"enabled": False}
    hybrid_sensitivity_data: dict[str, Any] = {"enabled": False}
    perf_metrics_data: dict[str, Any] = _disabled_section(
        "Performance capture not enabled."
    )
    root_causes_data: dict[str, Any] = _disabled_section(
        "Root-cause analysis not generated."
    )
    recommendations_data: dict[str, Any] = _disabled_section(
        "Recommendations not generated."
    )
    ltr_impact_data: dict[str, Any] = _disabled_section("LTR impact not available.")
    docs_payload: list[dict[str, Any]] = []
    query_cases = []
    baseline_schema: dict[str, Any] = {}
    inspect_payload: dict[str, Any] = {}
    perf_before: dict[str, Any] = {"baseline": {}, "shadow": {}}

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
        with stage("snapshot"):
            request_defaults = baseline_cfg.get("request_defaults", {})
            if snapshot:
                snapshot_data = load_snapshot(snapshot.resolve())
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

                write_json(Path(manifest.outputs["snapshot_json"]), snapshot_manifest)
                write_json(Path(manifest.outputs["snapshot_schema_json"]), baseline_schema)
                write_json(Path(manifest.outputs["snapshot_system_json"]), system)
                write_json(Path(manifest.outputs["snapshot_collection_json"]), collection_state)
                write_text(Path(manifest.outputs["snapshot_hash_txt"]), snapshot_hash + "\n")
                manifest.inputs["snapshot_path"] = str(snapshot.resolve())
            else:
                captured = capture_snapshot(
                    solr_url=baseline_url,
                    collection=baseline_collection,
                    out_dir=out,
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
                manifest.inputs["snapshot_path"] = str(out.resolve())

            write_json(Path(manifest.outputs["inspect_json"]), inspect_payload)
            manifest.baseline = {
                "solr_url": baseline_url,
                "collection": baseline_collection,
                "schema_hash": _hash_obj(baseline_schema),
                "snapshot_hash": snapshot_hash,
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
                changeset_path=changeset_path,
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
                "baseline_configset_hash": shadow_manifest.baseline_configset_hash,
                "shadow_configset_hash": shadow_manifest.shadow_configset_hash,
                "configset_isolated": shadow_manifest.configset_isolated,
                "configset_patch": shadow_manifest.configset_patch,
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
                    manifest.settings["vector_embedding_ingest"] = {
                        "source_type": embedding_source_type,
                        "path": embedding_source.get("path"),
                        "id_field": id_field,
                        "vector_field": vector_field,
                        "stats": embedding_stats,
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

        with stage("vector_validate"):
            if vector_runtime_cfg.enabled:
                vector_validation_data = validate_vector_setup(
                    baseline_schema=baseline_schema,
                    vector_cfg=vector_runtime_cfg,
                    query_cases=query_cases,
                    vector_dimension_override=vector_dimension_override,
                )
                write_json(
                    Path(manifest.outputs["vector_validation_json"]),
                    vector_validation_data,
                )
                manifest.settings["vector_validation"] = {
                    "summary": vector_validation_data.get("summary", {}),
                    "migration_required": vector_validation_data.get("migration_required", False),
                }
                if vector_validation_data.get("block_run"):
                    raise StageError("vector validation blocked run")
            else:
                vector_validation_data = {"enabled": False, "findings": []}
                write_json(Path(manifest.outputs["vector_validation_json"]), vector_validation_data)

        with stage("performance_prepare"):
            perf_cfg = changeset.raw.get("performance", {})
            if isinstance(perf_cfg, dict) and perf_cfg.get("enabled", False):
                cache_cfg = perf_cfg.get("caches", {})
                cache_names = (
                    cache_cfg.get("names")
                    if isinstance(cache_cfg, dict) and isinstance(cache_cfg.get("names"), list)
                    else None
                )
                perf_before = {
                    "baseline": collect_solr_runtime_snapshot(
                        client=baseline_client,
                        collection=baseline_collection,
                        cache_names=cache_names,
                        include_luke=bool(
                            (perf_cfg.get("index", {}) or {}).get("luke", True)
                            if isinstance(perf_cfg.get("index"), dict)
                            else True
                        ),
                    ),
                    "shadow": collect_solr_runtime_snapshot(
                        client=shadow_client,
                        collection=shadow_name or "",
                        cache_names=cache_names,
                        include_luke=bool(
                            (perf_cfg.get("index", {}) or {}).get("luke", True)
                            if isinstance(perf_cfg.get("index"), dict)
                            else True
                        ),
                    ),
                }
            else:
                perf_before = {"baseline": {}, "shadow": {}}

        with stage("replay"):
            if not shadow_name:
                raise StageError("Shadow name unavailable during replay stage")
            request_defaults = baseline_cfg.get("request_defaults", {})
            merged_defaults = merge_queryparams(request_defaults, changeset.changes)
            replay_cfg = changeset.replay if hasattr(changeset, "replay") else {}
            capture_cfg = {}
            if isinstance(replay_cfg, dict):
                capture_cfg = replay_cfg.get("capture", {})
                if not isinstance(capture_cfg, dict):
                    capture_cfg = {}
            manifest.settings["replay_capture"] = capture_cfg
            replay_data = run_replay(
                baseline_client=baseline_client,
                baseline_collection=baseline_collection,
                shadow_client=shadow_client,
                shadow_collection=shadow_name,
                queries=query_cases,
                request_defaults=merged_defaults,
                k=effective_k,
                capture_cfg=capture_cfg,
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

        with stage("scenario_replay"):
            if vector_runtime_cfg.enabled:
                if not shadow_name:
                    raise StageError("Shadow name unavailable during scenario_replay stage")
                request_defaults = baseline_cfg.get("request_defaults", {})
                merged_defaults = merge_queryparams(request_defaults, changeset.changes)
                vector_replay_data = run_vector_scenarios(
                    baseline_client=baseline_client,
                    baseline_collection=baseline_collection,
                    shadow_client=shadow_client,
                    shadow_collection=shadow_name,
                    queries=query_cases,
                    request_defaults=merged_defaults,
                    vector_cfg=vector_runtime_cfg,
                )
                replay_data["vector_scenarios"] = vector_replay_data
                write_json(Path(manifest.outputs["replay_json"]), replay_data)

                per_scenario_paths: dict[str, str] = {}
                scenario_results = vector_replay_data.get("scenario_results", {})
                if isinstance(scenario_results, dict):
                    for scenario_name, payload in scenario_results.items():
                        safe = "".join(
                            ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in scenario_name
                        )
                        scenario_path = out / f"replay_{safe}.json"
                        write_json(scenario_path, payload)
                        per_scenario_paths[scenario_name] = str(scenario_path.resolve())
                manifest.outputs["replay_scenarios"] = per_scenario_paths
            else:
                vector_replay_data = {"enabled": False, "scenario_results": {}}

        with stage("vector_compare"):
            if vector_runtime_cfg.enabled:
                vector_compare = compare_vector_hybrid(
                    scenario_replay=vector_replay_data,
                    top_k=int(vector_runtime_cfg.evaluation.get("topK", effective_k)),
                )
                compare_data["vector_hybrid"] = vector_compare
            else:
                compare_data["vector_hybrid"] = {"enabled": False}
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

        with stage("hybrid_sensitivity"):
            sensitivity_cfg = (
                vector_runtime_cfg.evaluation.get("sensitivity", {})
                if isinstance(vector_runtime_cfg.evaluation, dict)
                else {}
            )
            if vector_runtime_cfg.enabled and bool(sensitivity_cfg.get("enabled", False)):
                hybrid_sensitivity_data = run_hybrid_sensitivity(
                    scenario_replay=vector_replay_data,
                    weights=[float(w) for w in sensitivity_cfg.get("weights", [])],
                    top_k=int(vector_runtime_cfg.evaluation.get("topK", effective_k)),
                    candidate_pool=int(
                        vector_runtime_cfg.evaluation.get("candidate_pool", max(100, effective_k))
                    ),
                )
            else:
                hybrid_sensitivity_data = {"enabled": False, "weights": [], "scenarios": []}
            compare_data["hybrid_sensitivity"] = hybrid_sensitivity_data
            write_json(Path(manifest.outputs["hybrid_sensitivity_json"]), hybrid_sensitivity_data)
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

        with stage("rewrite_diff"):
            rewrite_cfg = eval_cfg.get("rewrite_diff", {})
            manifest.settings["rewrite_diff"] = rewrite_cfg if isinstance(rewrite_cfg, dict) else {}
            if isinstance(rewrite_cfg, dict) and rewrite_cfg.get("enabled", False):
                if not shadow_name:
                    raise StageError("Shadow name unavailable during rewrite_diff stage")
                synonym_rules = load_synonym_rules_from_changes(
                    changeset.changes,
                    changeset_path=str(changeset_path.resolve()),
                )
                has_synonym_changes = any(
                    op.get("op") == "schema.synonym.update"
                    for op in changeset.changes
                    if isinstance(op, dict)
                )
                rewrite_data = run_rewrite_diff(
                    baseline_client=baseline_client,
                    baseline_collection=baseline_collection,
                    shadow_client=shadow_client,
                    shadow_collection=shadow_name,
                    replay_pairs=replay_data.get("pairs", []),
                    diffs=compare_data.get("diffs", []),
                    k=effective_k,
                    rewrite_cfg=rewrite_cfg,
                    synonym_rules=synonym_rules,
                    has_synonym_changes=has_synonym_changes,
                )
                compare_data["rewrite_diff"] = rewrite_data
                rewrite_flags_by_qid = {
                    item.get("query_id"): item.get("risk_flags", [])
                    for item in rewrite_data.get("per_query", [])
                    if item.get("query_id") is not None
                }
                for diff_row in compare_data.get("diffs", []):
                    qid = diff_row.get("query_id")
                    flags = rewrite_flags_by_qid.get(qid, [])
                    if not isinstance(diff_row.get("risk_flags"), list):
                        diff_row["risk_flags"] = []
                    for flag in flags:
                        if flag not in diff_row["risk_flags"]:
                            diff_row["risk_flags"].append(flag)
                for diff_row in compare_data.get("top_regressions", []):
                    qid = diff_row.get("query_id")
                    flags = rewrite_flags_by_qid.get(qid, [])
                    if not isinstance(diff_row.get("risk_flags"), list):
                        diff_row["risk_flags"] = []
                    for flag in flags:
                        if flag not in diff_row["risk_flags"]:
                            diff_row["risk_flags"].append(flag)
            else:
                compare_data["rewrite_diff"] = {
                    "enabled": False,
                    "per_query": [],
                    "top_clause_deltas": [],
                    "top_synonym_changed": [],
                }
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

        with stage("performance_analyze"):
            perf_cfg = changeset.raw.get("performance", {})
            if isinstance(perf_cfg, dict) and perf_cfg.get("enabled", False):
                cache_cfg = perf_cfg.get("caches", {})
                cache_names = (
                    cache_cfg.get("names")
                    if isinstance(cache_cfg, dict) and isinstance(cache_cfg.get("names"), list)
                    else None
                )
                perf_after = {
                    "baseline": collect_solr_runtime_snapshot(
                        client=baseline_client,
                        collection=baseline_collection,
                        cache_names=cache_names,
                        include_luke=bool(
                            (perf_cfg.get("index", {}) or {}).get("luke", True)
                            if isinstance(perf_cfg.get("index"), dict)
                            else True
                        ),
                    ),
                    "shadow": collect_solr_runtime_snapshot(
                        client=shadow_client,
                        collection=shadow_name or "",
                        cache_names=cache_names,
                        include_luke=bool(
                            (perf_cfg.get("index", {}) or {}).get("luke", True)
                            if isinstance(perf_cfg.get("index"), dict)
                            else True
                        ),
                    ),
                }
                percentiles_capture = perf_cfg.get("capture")
                percentiles_cfg = (
                    percentiles_capture if isinstance(percentiles_capture, dict) else {}
                )
                percentiles = (
                    percentiles_cfg.get("percentiles")
                    if isinstance(percentiles_cfg.get("percentiles"), list)
                    else [50, 95, 99]
                )
                perf_metrics_data = analyze_performance(
                    replay_data=replay_data,
                    compare_data=compare_data,
                    baseline_snapshot=perf_after["baseline"],
                    shadow_snapshot=perf_after["shadow"],
                    changes=changeset.changes,
                    percentiles=[int(item) for item in percentiles],
                )
                perf_metrics_data["before"] = perf_before
                perf_metrics_data["after"] = perf_after
            else:
                perf_metrics_data = _disabled_section("Performance capture not enabled.")
                compare_data["performance"] = perf_metrics_data
            write_json(Path(manifest.outputs["perf_metrics_json"]), perf_metrics_data)
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

        with stage("root_cause"):
            root_causes_data = analyze_root_causes(
                compare_data=compare_data,
                changes=changeset.changes,
                baseline_request_defaults=baseline_cfg.get("request_defaults", {}),
            )
            compare_data["root_causes"] = root_causes_data
            write_json(Path(manifest.outputs["rootcauses_json"]), root_causes_data)
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

        with stage("recommend"):
            recommendations_data = build_recommendations(root_causes_data)
            compare_data["recommendations"] = recommendations_data
            write_json(Path(manifest.outputs["recommendations_json"]), recommendations_data)
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

        with stage("ltr"):
            ltr_impact_data = capture_ltr_impact(replay_data)
            compare_data["ltr_impact"] = ltr_impact_data
            write_json(Path(manifest.outputs["ltr_impact_json"]), ltr_impact_data)
            write_json(Path(manifest.outputs["compare_json"]), compare_data)

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
