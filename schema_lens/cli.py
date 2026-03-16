"""Typer CLI for SolrGuard."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

import typer

from schema_lens.changesets.parser import parse_changeset
from schema_lens.changesets.validator import validate_changeset
from schema_lens.ci.summarize import build_ci_summary_markdown
from schema_lens.compat import capabilities_for_version, compatibility_contract, detect_solr_version
from schema_lens.compat.adapters import (
    configset_upload_supported,
    metrics_supported,
    vector_supported,
)
from schema_lens.compare.diff import compare_replay
from schema_lens.compare.gate import evaluate_gate, load_gate_policy
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
from schema_lens.monitor.runner import run_monitor
from schema_lens.perf.solr_metrics import collect_solr_runtime_snapshot
from schema_lens.privacy import (
    mask_payload as privacy_mask_payload,
)
from schema_lens.plugins.contracts.auth import AuthProviderPlugin
from schema_lens.plugins.contracts.gate import GateEvaluatorPlugin, GateResult
from schema_lens.plugins.contracts.report import ReportRendererPlugin, ReportWidgetPlugin
from schema_lens.plugins.loader import load_plugin_runtime_config, load_plugins, validate_issues
from schema_lens.plugins.utils import normalize_plugin_payload
from schema_lens.queries.loader import load_queries
from schema_lens.queries.sampler import sample_queries
from schema_lens.queries.sanitize import sanitize_params
from schema_lens.queries.sources.solr_request_log import extract_queries_from_log
from schema_lens.recommend.engine import build_recommendations
from schema_lens.replay.runner import run_replay
from schema_lens.report.html_report import render_html_report
from schema_lens.report.json_report import build_report_json
from schema_lens.rollout import (
    build_alias_swap_plan,
    build_canary_plan,
    build_rollback_plan,
    compare_git_vs_live_configset,
    execute_alias_swap,
    verify_post_cutover,
)
from schema_lens.rootcause.engine import analyze_root_causes
from schema_lens.runtime import (
    build_segment_payload,
    build_and_enforce_privacy_report,
    cleanup_plugins,
    emit_observability_event,
    execute_plugins,
    get_plugin_config,
    get_plugins_by_type,
    plugin_artifact_paths,
    select_plugin,
    emit_observability_hook,
    finalize_governance_manifest,
    finalize_observability_outputs,
    initialize_governance,
    initialize_observability,
    initialize_plugins,
    initialize_privacy,
    initialize_security,
    load_or_extract_queries,
    load_or_sample_docs,
    run_compare_stage,
    run_explain_flow,
    run_ltr_impact,
    run_performance_analyze_flow,
    run_recommendations,
    run_replay_stage,
    run_root_cause,
    run_rewrite_diff_flow,
    run_snapshot_and_compat,
    run_vector_flow,
    write_report_artifacts,
)
from schema_lens.schema.preflight import run_preflight
from schema_lens.shadow.manager import cleanup_shadow, create_shadow
from schema_lens.snapshot.snapshotter import capture_snapshot
from schema_lens.security import (
    redact_payload,
)
from schema_lens.solr.admin_api import system_info
from schema_lens.solr.collections_api import cluster_status
from schema_lens.solr.schema_api import get_schema
from schema_lens.solr.update_api import post_docs
from schema_lens.util.git import current_git_commit_short
from schema_lens.util.io import ensure_dir, read_json, write_json, write_jsonl, write_text
from schema_lens.util.time import utc_now_iso
from schema_lens.vector.scenario_parser import parse_vector_runtime_config
from schema_lens.vector.validation import (
    validate_vector_setup,
)

app = typer.Typer(
    help=(
        "SolrGuard: Search Change Governance for Apache Solr. "
        "Legacy alias `schema-lens` is retained for backward compatibility."
    )
)
shadow_app = typer.Typer(help="Shadow collection operations")
queries_app = typer.Typer(help="Query source operations")
docs_app = typer.Typer(help="Document source operations")
golden_app = typer.Typer(help="Golden query operations")
ci_app = typer.Typer(help="CI summary operations")
api_app = typer.Typer(help="API service mode operations")
rollout_app = typer.Typer(help="GitOps and rollout orchestration operations")
plugins_app = typer.Typer(help="Plugin SDK operations")
app.add_typer(shadow_app, name="shadow")
app.add_typer(queries_app, name="queries")
app.add_typer(docs_app, name="docs")
app.add_typer(golden_app, name="golden")
app.add_typer(ci_app, name="ci")
app.add_typer(api_app, name="api")
app.add_typer(rollout_app, name="rollout")
app.add_typer(plugins_app, name="plugins")
LOGGER = logging.getLogger(__name__)
_PRIVACY_RUNTIME_CFG: dict[str, Any] = {}
_LEGACY_ALIAS_WARNED = False


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


def _write_json_maybe_redacted(
    path: Path,
    payload: dict[str, Any],
    *,
    redact: bool,
    extra_sensitive_keys: list[str] | None = None,
    privacy_cfg: dict[str, Any] | None = None,
) -> None:
    out_payload: dict[str, Any] = payload
    if redact:
        redacted = redact_payload(payload, extra_sensitive_keys=extra_sensitive_keys)
        out_payload = redacted if isinstance(redacted, dict) else payload
    active_privacy_cfg = privacy_cfg if isinstance(privacy_cfg, dict) else _PRIVACY_RUNTIME_CFG
    if isinstance(active_privacy_cfg, dict) and active_privacy_cfg.get("enabled"):
        masked = privacy_mask_payload(
            out_payload,
            salt=str(active_privacy_cfg.get("salt", "solrguard")),
            email=bool(active_privacy_cfg.get("mask_email", True)),
            uuid=bool(active_privacy_cfg.get("mask_uuid", True)),
            numeric_id_hash=bool(active_privacy_cfg.get("numeric_id_hash", True)),
            allowlist=active_privacy_cfg.get("allowlist") if isinstance(active_privacy_cfg.get("allowlist"), list) else None,
            denylist=active_privacy_cfg.get("denylist") if isinstance(active_privacy_cfg.get("denylist"), list) else None,
        )
        out_payload = masked if isinstance(masked, dict) else out_payload
    write_json(path, out_payload)


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


def _resolve_system_info_payload(
    *,
    solr_url: str | None,
    from_file: Path | None,
    verbose: bool,
) -> dict[str, Any]:
    if from_file is not None:
        payload = read_json(from_file.resolve())
        if not isinstance(payload, dict):
            raise typer.BadParameter("--from-file must point to a JSON object payload")
        return payload
    if solr_url is None:
        raise typer.BadParameter("Provide either --solr-url or --from-file")
    client = SolrHttpClient(solr_url, verbose=verbose)
    try:
        return system_info(client)
    finally:
        client.close()


@app.command("detect-capabilities")
def detect_capabilities(
    solr_url: str | None = typer.Option(None, "--solr-url"),
    from_file: Path | None = typer.Option(None, "--from-file", exists=True, readable=True),
    out: Path | None = typer.Option(None, "--out"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Detect Solr version and capability flags from target or fixture payload."""
    configure_logging(verbose)
    payload = _resolve_system_info_payload(solr_url=solr_url, from_file=from_file, verbose=verbose)
    version = detect_solr_version(payload)
    contract = compatibility_contract(version)
    contract["source"] = "file" if from_file is not None else "live_target"
    contract["version_detected"] = bool(version)
    if out is not None:
        write_json(out, contract)
        typer.echo(str(out))
        return
    typer.echo(json.dumps(contract, indent=2))


@app.command("compatibility")
def compatibility(
    target: str | None = typer.Option(None, "--target"),
    from_file: Path | None = typer.Option(None, "--from-file", exists=True, readable=True),
    out: Path | None = typer.Option(None, "--out"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Render compatibility and fallback summary for a target Solr or fixture."""
    configure_logging(verbose)
    payload = _resolve_system_info_payload(solr_url=target, from_file=from_file, verbose=verbose)
    version = detect_solr_version(payload)
    caps = capabilities_for_version(version)
    contract = compatibility_contract(version)
    summary = {
        "target": target or str(from_file),
        "solr_version": version,
        "support_tier": contract.get("support_tier"),
        "confidence": contract.get("confidence"),
        "missing_capabilities": contract.get("missing_capabilities", []),
        "fallbacks": contract.get("fallbacks", []),
        "vector_supported": bool(caps.get("vector_query_supported")),
        "structured_explain_supported": bool(caps.get("structured_explain_supported")),
        "metrics_supported": bool(caps.get("metrics_json_supported")),
        "package_manager_available": bool(caps.get("package_manager_available")),
    }
    if out is not None:
        write_json(out, summary)
        typer.echo(str(out))
        return
    typer.echo(json.dumps(summary, indent=2))


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
    api_url: str | None = typer.Option(None, "--api-url"),
    run_id: str | None = typer.Option(None, "--run-id"),
    port: int = typer.Option(8080, "--port"),
) -> None:
    """Serve a read-only local dashboard for run artifacts."""
    import uvicorn

    local_mode = run is not None or compare is not None
    api_mode = api_url is not None or run_id is not None
    if local_mode and api_mode:
        raise typer.BadParameter("Use either local artifact options or --api-url/--run-id")
    if not local_mode and not api_mode:
        raise typer.BadParameter("Provide --run/--compare or --api-url with --run-id")

    if api_mode:
        if not api_url or not run_id:
            raise typer.BadParameter("--api-url and --run-id are both required for API-backed mode")
        app_instance = create_dashboard_app(api_base_url=api_url, run_id=run_id)
    else:
        if run is not None and compare is not None:
            raise typer.BadParameter("Use only one of --run or --compare")
        source = run if run is not None else compare
        assert source is not None
        base_path = source if source.is_dir() else source.parent
        app_instance = create_dashboard_app(base_path.resolve())
    uvicorn.run(app_instance, host="127.0.0.1", port=port)


@api_app.command("serve")
def api_serve(
    data_dir: Path = typer.Option(Path(".solrguard_api"), "--data-dir", "--out"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8080, "--port"),
    local_only: bool = typer.Option(True, "--local-only/--no-local-only"),
    reload: bool = typer.Option(False, "--reload"),
    job_store: str = typer.Option("file", "--job-store", help="Job metadata backend: file|sqlite"),
    sqlite_path: Path | None = typer.Option(None, "--sqlite-path"),
    worker_mode: str = typer.Option(
        "inprocess",
        "--worker-mode",
        help="Worker mode: inline|inprocess|external",
    ),
) -> None:
    """Run SolrGuard REST API service."""
    import uvicorn
    from schema_lens.api import create_api_app

    ensure_dir(data_dir)
    app_instance = create_api_app(
        base_dir=data_dir.resolve(),
        local_only=local_only,
        job_store_backend=job_store,
        sqlite_path=sqlite_path,
        worker_mode=worker_mode,
    )
    uvicorn.run(app_instance, host=host, port=port, reload=reload)


@api_app.command("inspect")
def api_inspect(
    data_dir: Path = typer.Option(Path(".solrguard_api"), "--data-dir", "--out"),
    local_only: bool = typer.Option(True, "--local-only/--no-local-only"),
    job_store: str = typer.Option("file", "--job-store", help="Job metadata backend: file|sqlite"),
    sqlite_path: Path | None = typer.Option(None, "--sqlite-path"),
    worker_mode: str = typer.Option("inprocess", "--worker-mode"),
) -> None:
    """Inspect API service config and storage paths."""
    from schema_lens import __version__
    from schema_lens.api.storage import ApiStorage

    storage = ApiStorage(data_dir.resolve(), job_store_backend=job_store, sqlite_path=sqlite_path)
    payload = {
        "service": "solrguard-api",
        "version": __version__,
        "local_only": local_only,
        "base_dir": str(storage.base_dir),
        "jobs_dir": str(storage.jobs_dir),
        "runs_dir": str(storage.runs_dir),
        "logs_dir": str(storage.logs_dir),
        "job_store_backend": storage.job_store_backend,
        "sqlite_path": str(storage.sqlite_path) if storage.sqlite_path is not None else None,
        "worker_mode": worker_mode,
    }
    typer.echo(json.dumps(payload, indent=2))


@rollout_app.command("git-drift")
def rollout_git_drift(
    solr_url: str = typer.Option(..., "--solr-url"),
    collection: str = typer.Option(..., "--collection"),
    local_configset_dir: Path = typer.Option(..., "--local-configset-dir", exists=True, readable=True),
    out: Path = typer.Option(..., "--out"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Compare Git-tracked local configset against live cluster configset."""
    configure_logging(verbose)
    client = SolrHttpClient(solr_url, verbose=verbose)
    try:
        payload = compare_git_vs_live_configset(
            client=client,
            collection=collection,
            local_configset_dir=local_configset_dir,
        )
    finally:
        client.close()
    write_json(out, payload)
    typer.echo(str(out))


@rollout_app.command("canary-plan")
def rollout_canary_plan(
    baseline_collection: str = typer.Option(..., "--baseline-collection"),
    canary_collection: str = typer.Option(..., "--canary-collection"),
    traffic_sample_ratio: float = typer.Option(0.1, "--traffic-sample-ratio"),
    replay_query_count: int = typer.Option(500, "--replay-query-count"),
    policy_bundle: list[Path] | None = typer.Option(None, "--policy-bundle"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Generate deterministic canary rollout plan (dry-run)."""
    payload = build_canary_plan(
        baseline_collection=baseline_collection,
        canary_collection=canary_collection,
        traffic_sample_ratio=traffic_sample_ratio,
        replay_query_count=replay_query_count,
        policy_bundle_paths=[str(path.resolve()) for path in (policy_bundle or [])],
    )
    write_json(out, payload)
    typer.echo(str(out))


@rollout_app.command("alias-swap-plan")
def rollout_alias_swap_plan(
    alias: str = typer.Option(..., "--alias"),
    from_collection: str = typer.Option(..., "--from-collection"),
    to_collection: str = typer.Option(..., "--to-collection"),
    out: Path = typer.Option(..., "--out"),
    execute: bool = typer.Option(False, "--execute/--dry-run"),
    solr_url: str | None = typer.Option(None, "--solr-url"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Generate alias swap plan and optionally execute it."""
    payload = build_alias_swap_plan(
        alias=alias,
        source_collection=from_collection,
        target_collection=to_collection,
    )
    if execute:
        if not solr_url:
            raise typer.BadParameter("--solr-url is required when --execute is set")
        client = SolrHttpClient(solr_url, verbose=verbose)
        try:
            result = execute_alias_swap(client, alias=alias, target_collection=to_collection)
        finally:
            client.close()
        payload["mode"] = "execute"
        payload["result"] = result
    write_json(out, payload)
    typer.echo(str(out))


@rollout_app.command("rollback-plan")
def rollout_rollback_plan(
    alias: str = typer.Option(..., "--alias"),
    previous_collection: str = typer.Option(..., "--previous-collection"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Generate rollback plan artifact (dry-run)."""
    payload = build_rollback_plan(alias=alias, previous_collection=previous_collection)
    write_json(out, payload)
    typer.echo(str(out))


@rollout_app.command("verify-post-cutover")
def rollout_verify_post_cutover(
    canary_compare: Path = typer.Option(..., "--canary-compare", exists=True, readable=True),
    prod_compare: Path = typer.Option(..., "--prod-compare", exists=True, readable=True),
    overlap_threshold: float = typer.Option(0.7, "--overlap-threshold"),
    high_risk_threshold_pct: float = typer.Option(5.0, "--high-risk-threshold-pct"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Verify post-cutover quality gates from canary/prod compare artifacts."""
    canary_payload = read_json(canary_compare)
    prod_payload = read_json(prod_compare)
    payload = verify_post_cutover(
        canary_compare=canary_payload if isinstance(canary_payload, dict) else {},
        prod_compare=prod_payload if isinstance(prod_payload, dict) else {},
        overlap_threshold=overlap_threshold,
        high_risk_threshold_pct=high_risk_threshold_pct,
    )
    write_json(out, payload)
    typer.echo(str(out))


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
    """Run full end-to-end SolrGuard governance workflow."""
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
            "compat_json": str((out / "compat.json").resolve()),
            "governance_json": str((out / "governance.json").resolve()),
            "privacy_json": str((out / "privacy.json").resolve()),
            "schema_risk_json": str((out / "schema_risk.json").resolve()),
            "shadow_json": str((out / "shadow.json").resolve()),
            "docs_sample_jsonl": str((out / "docs_sample.jsonl").resolve()),
            "queries_extracted_jsonl": str((out / "queries_extracted.jsonl").resolve()),
            "replay_json": str((out / "replay.json").resolve()),
            "compare_json": str((out / "compare.json").resolve()),
            "vector_validation_json": str((out / "vector_validation.json").resolve()),
            "hybrid_sensitivity_json": str((out / "hybrid_sensitivity.json").resolve()),
            "perf_metrics_json": str((out / "perf_metrics.json").resolve()),
            "segments_json": str((out / "segments.json").resolve()),
            "rootcauses_json": str((out / "rootcauses.json").resolve()),
            "recommendations_json": str((out / "recommendations.json").resolve()),
            "env_compare_json": str((out / "env_compare.json").resolve()),
            "monitor_history_jsonl": str((out / "monitor_history.jsonl").resolve()),
            "ltr_impact_json": str((out / "ltr_impact.json").resolve()),
            "audit_json": str((out / "audit.json").resolve()),
            "observability_events_jsonl": str((out / "observability_events.jsonl").resolve()),
            "otel_spans_json": str((out / "otel_spans.json").resolve()),
            "prometheus_metrics_txt": str((out / "prometheus_metrics.prom").resolve()),
            "webhook_deliveries_json": str((out / "webhook_deliveries.json").resolve()),
            "plugins_json": str((out / "plugins.json").resolve()),
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

    queries_path: Path | None = None
    if query_source_type in {"file", "log"}:
        queries_path = _resolve_path(changeset_path, queries_source["path"])
        manifest.inputs["queries_path"] = str(queries_path)
    else:
        manifest.inputs["queries_path"] = "<provided_by_plugin>"
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

    baseline_client: SolrHttpClient | None = None
    shadow_client: SolrHttpClient | None = None
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
    plugins_runtime = None
    compat_caps: dict[str, Any] = {}
    observability_runtime = None
    governance_data: dict[str, Any] = {"enabled": False}
    governance_sign_secret: str | None = None
    privacy_runtime_cfg: dict[str, Any] = {"enabled": False}
    persist_sensitive_effective = True
    plugin_gate_results: list[dict[str, Any]] = []
    plugin_report_sections_json: list[dict[str, Any]] = []
    plugin_report_sections_html: list[dict[str, Any]] = []

    def emit_event(event_type: str, payload: dict[str, Any]) -> None:
        if observability_runtime is None:
            return
        emit_observability_event(
            observability_runtime,
            event_type=event_type,
            timestamp=utc_now_iso(),
            run_id=run_id,
            payload=payload,
        )
    security_profile_name = "local-dev"
    security_redact_artifacts = False
    security_persist_sensitive = True
    security_extra_sensitive_keys: list[str] = []

    def stage(name: str):
        class StageCtx:
            def __enter__(self_inner):
                started_at = utc_now_iso()
                manifest.stages[name] = {"started_at": started_at, "status": "running"}
                if observability_runtime is not None:
                    observability_runtime.otel.start_span(
                        name,
                        name=name,
                        started_at=started_at,
                        attributes={
                            "run_id": run_id,
                            "baseline_url": baseline_url,
                            "baseline_collection": baseline_collection,
                            "shadow_url": shadow_url,
                            "feature.vector_enabled": bool(vector_runtime_cfg.enabled),
                        },
                    )
                self_inner.started = perf_counter()
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                elapsed = perf_counter() - self_inner.started
                manifest.stages[name]["duration_seconds"] = round(elapsed, 3)
                if observability_runtime is not None:
                    observability_runtime.otel.end_span(name, ended_at=utc_now_iso())
                if exc:
                    manifest.stages[name]["status"] = "failed"
                    manifest.stages[name]["error"] = str(exc)
                else:
                    manifest.stages[name]["status"] = "ok"
                return False

        return StageCtx()

    try:
        with stage("observability_init"):
            observability_runtime = initialize_observability(
                changeset_raw=changeset.raw,
                manifest_settings=manifest.settings,
            )
            emit_event(
                "run_started",
                {
                    "baseline_collection": baseline_collection,
                    "k": effective_k,
                },
            )

        with stage("governance_init"):
            governance_runtime = initialize_governance(
                changeset_raw=changeset.raw,
                changeset_path=changeset_path,
            )
            governance_data = governance_runtime.data
            governance_sign_secret = governance_runtime.sign_secret

            manifest.settings["governance"] = governance_data
            _write_json_maybe_redacted(
                Path(manifest.outputs["governance_json"]),
                governance_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("plugins_init"):
            plugins_runtime = initialize_plugins(
                changeset_raw=changeset.raw,
                changeset_path=changeset_path,
                run_id=run_id,
                out_dir=out,
                manifest_payload=manifest.to_dict(),
                logger=LOGGER,
            )
            manifest.settings["plugins"] = plugins_runtime.settings
            emit_observability_hook(
                runtime=plugins_runtime,
                event="on_run_started",
                run_context={"run_id": run_id, "changeset_path": str(changeset_path.resolve())},
                out_dir=out,
                logger=LOGGER,
            )

        with stage("security_init"):
            auth_plugins = [plugin for plugin in get_plugins_by_type(plugins_runtime, "auth") if isinstance(plugin, AuthProviderPlugin)]
            security_runtime = initialize_security(
                changeset_raw=changeset.raw,
                changeset_path=changeset_path,
                baseline_cfg=baseline_cfg,
                shadow_cfg=shadow_cfg,
                active_auth_plugins=auth_plugins,
                run_id=run_id,
                started=started,
                baseline_url=baseline_url,
                baseline_collection=baseline_collection,
                shadow_url=shadow_url,
                verbose=verbose,
                write_audit=lambda payload, redact, extra_keys: _write_json_maybe_redacted(
                    Path(manifest.outputs["audit_json"]),
                    payload,
                    redact=redact,
                    extra_sensitive_keys=extra_keys,
                ),
            )
            security_profile_name = security_runtime.profile_name
            security_redact_artifacts = security_runtime.redact_artifacts
            security_persist_sensitive = security_runtime.persist_sensitive_artifacts
            security_extra_sensitive_keys = security_runtime.extra_sensitive_keys
            baseline_client = security_runtime.baseline_client
            shadow_client = security_runtime.shadow_client
            manifest.settings["security"] = security_runtime.manifest_security

        with stage("privacy_init"):
            global _PRIVACY_RUNTIME_CFG
            privacy_runtime = initialize_privacy(
                changeset_raw=changeset.raw,
                security_persist_sensitive=security_persist_sensitive,
            )
            privacy_runtime_cfg = privacy_runtime.config
            _PRIVACY_RUNTIME_CFG = privacy_runtime_cfg
            persist_sensitive_effective = privacy_runtime.persist_sensitive_effective
            manifest.settings["privacy"] = {
                "enabled": privacy_runtime_cfg["enabled"],
                "profile": privacy_runtime_cfg["profile"],
                "export_safe": privacy_runtime_cfg["export_safe"],
                "raw_doc_suppression": privacy_runtime_cfg["raw_doc_suppression"],
                "hashed_doc_id_only": privacy_runtime_cfg["hashed_doc_id_only"],
                "persist_sensitive": privacy_runtime_cfg["persist_sensitive"],
            }
            _write_json_maybe_redacted(
                Path(manifest.outputs["privacy_json"]),
                {
                    "enabled": privacy_runtime_cfg["enabled"],
                    "profile": privacy_runtime_cfg["profile"],
                    "export_safe": privacy_runtime_cfg["export_safe"],
                },
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
                privacy_cfg=privacy_runtime_cfg,
            )

        with stage("snapshot"):
            if baseline_client is None or shadow_client is None:
                raise StageError("security_init failed to initialize clients")
            snapshot_runtime = run_snapshot_and_compat(
                snapshot_path=snapshot,
                baseline_url=baseline_url,
                baseline_collection=baseline_collection,
                out_dir=out,
                request_defaults=baseline_cfg.get("request_defaults", {}),
                verbose=verbose,
                outputs=manifest.outputs,
                manifest_inputs=manifest.inputs,
            )
            baseline_schema = snapshot_runtime.baseline_schema
            inspect_payload = snapshot_runtime.inspect_payload
            compat_caps = snapshot_runtime.compat_caps
            compat_payload = snapshot_runtime.compat_payload
            snapshot_hash = snapshot_runtime.snapshot_hash

            _write_json_maybe_redacted(
                Path(manifest.outputs["compat_json"]),
                compat_payload,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )
            manifest.settings["compatibility"] = compat_payload
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
            has_configset_patch_changes = any(
                isinstance(op, dict)
                and op.get("op") in {"schema.synonym.update", "schema.stopwords.update"}
                for op in changeset.changes
            )
            if has_configset_patch_changes and not configset_upload_supported(compat_caps):
                manifest.settings.setdefault("compatibility", {}).setdefault(
                    "fallbacks", []
                ).append(
                    {
                        "feature": "configset_upload",
                        "reason": "configset_upload_supported capability is unavailable",
                    }
                )
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
            try:
                doc_source_plugin_name = str(docs_source.get("provider", "")).strip()
                selected_doc_plugin = (
                    select_plugin(
                        plugins_runtime,
                        plugin_type="doc_source",
                        plugin_name=doc_source_plugin_name,
                    )
                    if docs_source_type == "plugin"
                    else None
                )
                docs_payload = load_or_sample_docs(
                    docs_source_type=docs_source_type,
                    docs_source=docs_source if isinstance(docs_source, dict) else {},
                    docs_path=docs_path,
                    data_cfg=data_cfg if isinstance(data_cfg, dict) else {},
                    baseline_url=baseline_url,
                    baseline_collection=baseline_collection,
                    batch_size=batch_size,
                    manifest_inputs=manifest.inputs,
                    manifest_settings=manifest.settings,
                    outputs=manifest.outputs,
                    persist_sensitive_effective=bool(persist_sensitive_effective),
                    privacy_runtime_cfg=privacy_runtime_cfg,
                    vector_runtime_cfg=vector_runtime_cfg,
                    changeset_path=changeset_path,
                    verbose=verbose,
                    docs_source_plugins=[selected_doc_plugin] if selected_doc_plugin is not None else [],
                    plugin_source_config=get_plugin_config(plugins_runtime, doc_source_plugin_name),
                    plugin_context={
                        "run_id": run_id,
                        "changeset": changeset.raw,
                        "changeset_path": str(changeset_path.resolve()),
                    },
                )
            except ValueError as exc:
                raise StageError(str(exc)) from exc

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
            query_source_plugin_name = str(queries_source.get("provider", "")).strip()
            selected_query_plugin = (
                select_plugin(
                    plugins_runtime,
                    plugin_type="query_source",
                    plugin_name=query_source_plugin_name,
                )
                if query_source_type == "plugin"
                else None
            )
            query_cases = load_or_extract_queries(
                query_source_type=query_source_type,
                queries_source=queries_source if isinstance(queries_source, dict) else {},
                queries_path=queries_path if queries_path is not None else changeset_path,
                query_cfg=query_cfg if isinstance(query_cfg, dict) else {},
                outputs=manifest.outputs,
                manifest_inputs=manifest.inputs,
                manifest_settings=manifest.settings,
                persist_sensitive_effective=bool(persist_sensitive_effective),
                query_source_plugins=[selected_query_plugin] if selected_query_plugin is not None else [],
                plugin_source_config=get_plugin_config(plugins_runtime, query_source_plugin_name),
                plugin_context={
                    "run_id": run_id,
                    "changeset": changeset.raw,
                    "changeset_path": str(changeset_path.resolve()),
                },
            )

        with stage("vector_validate"):
            if vector_runtime_cfg.enabled:
                if not vector_supported(compat_caps):
                    vector_runtime_cfg.enabled = False
                    vector_validation_data = {
                        "enabled": False,
                        "reason": "vector_query_supported capability is unavailable for this Solr version",
                    }
                    manifest.settings["vector_validation"] = {
                        "summary": {},
                        "migration_required": False,
                        "compatibility_skipped": True,
                    }
                else:
                    vector_validation_data = validate_vector_setup(
                        baseline_schema=baseline_schema,
                        vector_cfg=vector_runtime_cfg,
                        query_cases=query_cases,
                        vector_dimension_override=vector_dimension_override,
                    )
                    manifest.settings["vector_validation"] = {
                        "summary": vector_validation_data.get("summary", {}),
                        "migration_required": vector_validation_data.get("migration_required", False),
                    }
                    if vector_validation_data.get("block_run"):
                        raise StageError("vector validation blocked run")
                write_json(
                    Path(manifest.outputs["vector_validation_json"]),
                    vector_validation_data,
                )
            else:
                vector_validation_data = {"enabled": False, "findings": []}
                write_json(Path(manifest.outputs["vector_validation_json"]), vector_validation_data)

        with stage("performance_prepare"):
            perf_cfg = changeset.raw.get("performance", {})
            if (
                isinstance(perf_cfg, dict)
                and perf_cfg.get("enabled", False)
                and metrics_supported(compat_caps)
            ):
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
            replay_cfg = changeset.replay if hasattr(changeset, "replay") else {}
            replay_data, capture_cfg = run_replay_stage(
                baseline_client=baseline_client,
                baseline_collection=baseline_collection,
                shadow_client=shadow_client,
                shadow_collection=shadow_name,
                query_cases=query_cases,
                request_defaults=baseline_cfg.get("request_defaults", {}),
                changes=changeset.changes,
                replay_cfg=replay_cfg if isinstance(replay_cfg, dict) else {},
                k=effective_k,
                baseline_url=baseline_url,
                shadow_url=shadow_url,
            )
            manifest.settings["replay_capture"] = capture_cfg
            _write_json_maybe_redacted(
                Path(manifest.outputs["replay_json"]),
                replay_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )
            manifest.stats["queries_run"] = len(query_cases)
            manifest.stats["failures"] = replay_data.get("stats", {}).get("failures", 0)

        with stage("compare"):
            compare_data = run_compare_stage(
                replay_data=replay_data,
                k=effective_k,
                schema_risk_data=schema_risk_data,
                compatibility=manifest.settings.get("compatibility", {}),
                governance=manifest.settings.get("governance", {}),
            )
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("segment_report"):
            segment_report = build_segment_payload(
                changeset_raw=changeset.raw,
                compare_data=compare_data,
            )
            compare_data["segments"] = segment_report
            _write_json_maybe_redacted(
                Path(manifest.outputs["segments_json"]),
                segment_report,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("scenario_replay"):
            try:
                vector_flow = run_vector_flow(
                    vector_runtime_cfg=vector_runtime_cfg,
                    shadow_name=shadow_name,
                    baseline_client=baseline_client,
                    baseline_collection=baseline_collection,
                    shadow_client=shadow_client,
                    query_cases=query_cases,
                    baseline_request_defaults=baseline_cfg.get("request_defaults", {}),
                    changes=changeset.changes,
                    effective_k=effective_k,
                    replay_data=replay_data,
                    out_dir=out,
                )
            except ValueError as exc:
                raise StageError(str(exc)) from exc
            vector_replay_data = vector_flow["vector_replay_data"]
            manifest.outputs["replay_scenarios"] = vector_flow["replay_scenarios"]
            if vector_runtime_cfg.enabled:
                _write_json_maybe_redacted(
                    Path(manifest.outputs["replay_json"]),
                    replay_data,
                    redact=security_redact_artifacts,
                    extra_sensitive_keys=security_extra_sensitive_keys,
                )

        with stage("vector_compare"):
            compare_data["vector_hybrid"] = vector_flow["vector_hybrid"]
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("hybrid_sensitivity"):
            hybrid_sensitivity_data = vector_flow["hybrid_sensitivity"]
            compare_data["hybrid_sensitivity"] = hybrid_sensitivity_data
            write_json(Path(manifest.outputs["hybrid_sensitivity_json"]), hybrid_sensitivity_data)
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("rewrite_diff"):
            try:
                rewrite_data, rewrite_settings = run_rewrite_diff_flow(
                    eval_cfg=eval_cfg if isinstance(eval_cfg, dict) else {},
                    changes=changeset.changes,
                    changeset_path=changeset_path,
                    baseline_client=baseline_client,
                    baseline_collection=baseline_collection,
                    shadow_client=shadow_client,
                    shadow_name=shadow_name,
                    replay_data=replay_data,
                    compare_data=compare_data,
                    effective_k=effective_k,
                )
            except ValueError as exc:
                raise StageError(str(exc)) from exc
            manifest.settings["rewrite_diff"] = rewrite_settings
            compare_data["rewrite_diff"] = rewrite_data
            if not bool(rewrite_data.get("enabled", False)):
                _write_json_maybe_redacted(
                    Path(manifest.outputs["compare_json"]),
                    compare_data,
                    redact=security_redact_artifacts,
                    extra_sensitive_keys=security_extra_sensitive_keys,
                )

        with stage("explain"):
            bundles, explain_fallback = run_explain_flow(
                eval_cfg=eval_cfg if isinstance(eval_cfg, dict) else {},
                compat_caps=compat_caps,
                baseline_client=baseline_client,
                baseline_collection=baseline_collection,
                shadow_client=shadow_client,
                shadow_name=shadow_name,
                replay_data=replay_data,
                compare_data=compare_data,
                effective_k=effective_k,
            )
            if explain_fallback is not None:
                compare_data.setdefault("compatibility", {}).setdefault("fallbacks", []).append(explain_fallback)
            if bundles:
                compare_data["explain_bundles"] = bundles
                _write_json_maybe_redacted(
                    Path(manifest.outputs["compare_json"]),
                    compare_data,
                    redact=security_redact_artifacts,
                    extra_sensitive_keys=security_extra_sensitive_keys,
                )
            else:
                compare_data["explain_bundles"] = []

        with stage("performance_analyze"):
            perf_metrics_data = run_performance_analyze_flow(
                changeset_raw=changeset.raw,
                compat_caps=compat_caps,
                baseline_client=baseline_client,
                baseline_collection=baseline_collection,
                shadow_client=shadow_client,
                shadow_name=shadow_name,
                replay_data=replay_data,
                compare_data=compare_data,
                changes=changeset.changes,
                perf_before=perf_before,
                disabled_section=_disabled_section,
            )
            compare_data["performance"] = perf_metrics_data
            write_json(Path(manifest.outputs["perf_metrics_json"]), perf_metrics_data)
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("root_cause"):
            root_causes_data = run_root_cause(
                compare_data=compare_data,
                changes=changeset.changes,
                baseline_request_defaults=baseline_cfg.get("request_defaults", {}),
            )
            compare_data["root_causes"] = root_causes_data
            write_json(Path(manifest.outputs["rootcauses_json"]), root_causes_data)
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("recommend"):
            recommendations_data = run_recommendations(root_causes=root_causes_data)
            compare_data["recommendations"] = recommendations_data
            write_json(Path(manifest.outputs["recommendations_json"]), recommendations_data)
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("ltr"):
            ltr_impact_data = run_ltr_impact(replay_data=replay_data)
            compare_data["ltr_impact"] = ltr_impact_data
            write_json(Path(manifest.outputs["ltr_impact_json"]), ltr_impact_data)
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        with stage("plugins_gate"):
            if plugins_runtime is not None:
                for plugin in get_plugins_by_type(plugins_runtime, "gate"):
                    if not isinstance(plugin, GateEvaluatorPlugin):
                        continue
                    plugin_policy = get_plugin_config(plugins_runtime, plugin.metadata.name)
                    try:
                        raw_result = plugin.evaluate(
                            plugin_policy,
                            {
                                "compare_data": compare_data,
                                "replay_data": replay_data,
                                "manifest": manifest.to_dict(),
                            },
                        )
                        result_payload = (
                            asdict(raw_result)
                            if isinstance(raw_result, GateResult)
                            else (raw_result if isinstance(raw_result, dict) else {"value": raw_result})
                        )
                        result_payload = normalize_plugin_payload(result_payload)
                        plugin_gate_results.append(
                            {
                                "plugin": plugin.metadata.name,
                                "plugin_type": plugin.metadata.plugin_type,
                                "result": result_payload,
                            }
                        )
                        artifact_paths = plugin_artifact_paths(out, plugin.metadata.name)
                        write_json(
                            artifact_paths.result_json,
                            {"plugin": plugin.metadata.name, "phase": "gate", "result": result_payload},
                        )
                    except Exception as exc:  # noqa: BLE001
                        issue = {
                            "plugin": plugin.metadata.name,
                            "plugin_type": plugin.metadata.plugin_type,
                            "stage": "gate",
                            "message": str(exc),
                            "fatal": bool(plugins_runtime.strict),
                        }
                        plugins_runtime.issues.append(issue)
                        if plugins_runtime.strict:
                            raise StageError(f"gate plugin failed ({plugin.metadata.name}): {exc}") from exc
                        LOGGER.warning("Gate plugin failed for %s: %s", plugin.metadata.name, exc)
                if plugin_gate_results:
                    compare_data["plugin_gates"] = plugin_gate_results

        with stage("plugins_report"):
            if plugins_runtime is not None:
                for plugin in get_plugins_by_type(plugins_runtime, "report"):
                    if not isinstance(plugin, (ReportRendererPlugin, ReportWidgetPlugin)):
                        continue
                    try:
                        json_section = plugin.render_json_section(
                            {"run_id": run_id, "changeset": changeset.raw},
                            {"compare_data": compare_data, "replay_data": replay_data, "manifest": manifest.to_dict()},
                        )
                        if isinstance(json_section, dict):
                            plugin_report_sections_json.append(
                                {"plugin": plugin.metadata.name, "section": json_section}
                            )
                        html_section = plugin.render_html_section(
                            {"run_id": run_id, "changeset": changeset.raw},
                            {"compare_data": compare_data, "replay_data": replay_data, "manifest": manifest.to_dict()},
                        )
                        if isinstance(html_section, str) and html_section.strip():
                            plugin_report_sections_html.append(
                                {"plugin": plugin.metadata.name, "html": html_section}
                            )
                        artifact_paths = plugin_artifact_paths(out, plugin.metadata.name)
                        write_json(
                            artifact_paths.result_json,
                            {
                                "plugin": plugin.metadata.name,
                                "phase": "report",
                                "json_section": json_section if isinstance(json_section, dict) else {},
                                "html_section": html_section if isinstance(html_section, str) else "",
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        issue = {
                            "plugin": plugin.metadata.name,
                            "plugin_type": plugin.metadata.plugin_type,
                            "stage": "report",
                            "message": str(exc),
                            "fatal": bool(plugins_runtime.strict),
                        }
                        plugins_runtime.issues.append(issue)
                        if plugins_runtime.strict:
                            raise StageError(f"report plugin failed ({plugin.metadata.name}): {exc}") from exc
                        LOGGER.warning("Report plugin failed for %s: %s", plugin.metadata.name, exc)

        with stage("plugins_execute"):
            if plugins_runtime is None:
                compare_data["plugins"] = {"enabled": False, "results": [], "issues": []}
            else:
                compare_data["plugins"] = execute_plugins(
                    runtime=plugins_runtime,
                    run_id=run_id,
                    out_dir=out,
                    changeset_path=changeset_path,
                    changeset_raw=changeset.raw,
                    manifest_payload=manifest.to_dict(),
                    compare_data=compare_data,
                    replay_data=replay_data,
                    logger=LOGGER,
                )
                if plugin_gate_results:
                    compare_data["plugins"]["gate_results"] = plugin_gate_results
                if plugin_report_sections_json or plugin_report_sections_html:
                    compare_data["plugins"]["report_sections"] = {
                        "json": plugin_report_sections_json,
                        "html": plugin_report_sections_html,
                    }
                manifest.settings["plugins_runtime"] = {
                    "loaded_plugins": compare_data["plugins"].get("loaded_plugins", []),
                    "failed_plugins": compare_data["plugins"].get("failed_plugins", []),
                    "warnings": compare_data["plugins"].get("warnings", []),
                    "output_artifacts": compare_data["plugins"].get("output_artifacts", {}),
                }
            _write_json_maybe_redacted(
                Path(manifest.outputs["plugins_json"]),
                compare_data["plugins"],
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )
            if plugin_gate_results:
                failed_gate = next(
                    (
                        result
                        for result in plugin_gate_results
                        if isinstance(result.get("result"), dict)
                        and result["result"].get("passed") is False
                    ),
                    None,
                )
                if failed_gate is not None:
                    emit_observability_hook(
                        runtime=plugins_runtime,
                        event="on_gate_failed",
                        run_context={"run_id": run_id, "changeset_path": str(changeset_path.resolve())},
                        payload=failed_gate,
                        out_dir=out,
                        logger=LOGGER,
                    )

        with stage("report"):
            write_report_artifacts(
                manifest_payload=manifest.to_dict(),
                compare_data=compare_data,
                replay_data=replay_data,
                report_json_path=Path(manifest.outputs["report_json"]),
                report_html_path=Path(manifest.outputs["report_html"]),
                template_dir=Path(__file__).parent / "report" / "templates",
                write_redacted_json=_write_json_maybe_redacted,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
                plugin_report_sections={
                    "json": plugin_report_sections_json,
                    "html": plugin_report_sections_html,
                },
            )

    except Exception as exc:  # noqa: BLE001
        raise StageError(f"run failed: {exc}") from exc

    finally:
        with stage("cleanup"):
            if plugins_runtime is not None:
                cleanup_plugins(
                    runtime=plugins_runtime,
                    run_id=run_id,
                    out_dir=out,
                    changeset_path=changeset_path,
                    changeset_raw=changeset.raw,
                    manifest_payload=manifest.to_dict(),
                    logger=LOGGER,
                )
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
        gov_settings = manifest.settings.get("governance", {})
        if isinstance(gov_settings, dict) and gov_settings.get("enabled"):
            finalized_governance = finalize_governance_manifest(
                manifest_payload=manifest.to_dict(),
                governance_settings=gov_settings,
                sign_secret=governance_sign_secret,
            )
            manifest.settings["governance"] = finalized_governance
            _write_json_maybe_redacted(
                Path(manifest.outputs["governance_json"]),
                finalized_governance,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        run_failed = any(
            isinstance(stage_info, dict) and stage_info.get("status") == "failed"
            for stage_info in manifest.stages.values()
        )
        high_risk_percent = float(
            (compare_data.get("summary", {}) or {}).get("high_risk_percent", 0.0)
            if isinstance(compare_data, dict)
            else 0.0
        )
        if high_risk_percent > 0:
            emit_event(
                "drift_detected",
                {"high_risk_percent": high_risk_percent},
            )
        emit_event(
            "run_completed",
            {
                "status": "failed" if run_failed else "succeeded",
                "duration_seconds": manifest.stats["duration_seconds"],
                "queries_run": manifest.stats.get("queries_run", 0),
            },
        )
        emit_observability_hook(
            runtime=plugins_runtime,
            event="on_run_completed",
            run_context={"run_id": run_id, "changeset_path": str(changeset_path.resolve())},
            payload={"compare_data": compare_data, "replay_data": replay_data, "manifest": manifest.to_dict()},
            out_dir=out,
            logger=LOGGER,
        )

        observability_cfg = observability_runtime.config if observability_runtime is not None else {}
        compare_data["observability"] = finalize_observability_outputs(
            observability_runtime=observability_runtime,
            observability_cfg=observability_cfg,
            compare_data=compare_data,
            failed=run_failed,
            outputs=manifest.outputs,
        )
        if isinstance(compare_data, dict) and compare_data:
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        privacy_report_payload, _ = build_and_enforce_privacy_report(
            out_dir=out,
            runtime_cfg=privacy_runtime_cfg,
            persist_sensitive_effective=bool(persist_sensitive_effective),
        )
        _write_json_maybe_redacted(
            Path(manifest.outputs["privacy_json"]),
            privacy_report_payload,
            redact=security_redact_artifacts,
            extra_sensitive_keys=security_extra_sensitive_keys,
            privacy_cfg=privacy_runtime_cfg,
        )
        manifest.settings["privacy"]["report"] = privacy_report_payload
        compare_data["privacy"] = privacy_report_payload
        if isinstance(compare_data, dict) and compare_data:
            _write_json_maybe_redacted(
                Path(manifest.outputs["compare_json"]),
                compare_data,
                redact=security_redact_artifacts,
                extra_sensitive_keys=security_extra_sensitive_keys,
            )

        _write_json_maybe_redacted(
            Path(manifest.outputs["run_manifest"]),
            manifest.to_dict(),
            redact=security_redact_artifacts,
            extra_sensitive_keys=security_extra_sensitive_keys,
        )
        _PRIVACY_RUNTIME_CFG = {}
        if baseline_client is not None:
            baseline_client.close()
        if shadow_client is not None:
            shadow_client.close()

    typer.echo(str(Path(manifest.outputs["report_json"])))
    typer.echo(str(Path(manifest.outputs["report_html"])))


@plugins_app.command("list")
def plugins_list(
    changeset: Path | None = typer.Option(None, "--changeset", exists=True, readable=True),
) -> None:
    """List discovered plugins with metadata."""
    raw: dict[str, Any] = {}
    changeset_path = Path.cwd() / "changeset.yaml"
    if changeset is not None:
        parsed = parse_changeset(changeset)
        raw = parsed.raw
        changeset_path = changeset
    cfg = load_plugin_runtime_config(raw, changeset_path)
    loaded = load_plugins(cfg, base_dir=changeset_path.parent.resolve())
    payload = {
        "enabled": cfg.enabled,
        "strict_mode": cfg.strict_mode,
        "issues": [issue.to_dict() for issue in loaded.issues],
        "plugins": loaded.registry.list_plugins(),
        "active": [plugin.metadata.name for plugin in loaded.active],
    }
    typer.echo(json.dumps(payload, indent=2))


@plugins_app.command("validate")
def plugins_validate(
    changeset: Path = typer.Option(..., "--changeset", exists=True, readable=True),
) -> None:
    """Validate plugin discovery and strict-mode compatibility."""
    parsed = parse_changeset(changeset)
    cfg = load_plugin_runtime_config(parsed.raw, changeset)
    loaded = load_plugins(cfg, base_dir=changeset.parent.resolve())
    validate_issues(loaded.issues, strict=cfg.strict_mode)
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "issues": [issue.to_dict() for issue in loaded.issues],
                "active": [plugin.metadata.name for plugin in loaded.active],
            },
            indent=2,
        )
    )


@plugins_app.command("inspect")
def plugins_inspect(
    plugin_name: str = typer.Argument(...),
    changeset: Path = typer.Option(..., "--changeset", exists=True, readable=True),
) -> None:
    """Inspect a single plugin's metadata and config."""
    parsed = parse_changeset(changeset)
    cfg = load_plugin_runtime_config(parsed.raw, changeset)
    loaded = load_plugins(cfg, base_dir=changeset.parent.resolve())
    plugin = loaded.registry.get_by_name(plugin_name)
    if plugin is None:
        raise typer.BadParameter(f"Plugin not found: {plugin_name}")
    plugin_config = cfg.config.get(plugin_name, {})
    payload = {
        "name": plugin.metadata.name,
        "version": plugin.metadata.version,
        "description": plugin.metadata.description,
        "plugin_type": plugin.metadata.plugin_type,
        "compatible_schema_lens_version": plugin.metadata.compatible_schema_lens_version,
        "capabilities": plugin.metadata.capabilities,
        "enabled": plugin in loaded.active,
        "config": plugin.redact(plugin_config if isinstance(plugin_config, dict) else {}),
    }
    typer.echo(json.dumps(payload, indent=2))


@app.callback()
def main() -> None:
    """SolrGuard command group."""
    global _LEGACY_ALIAS_WARNED
    invoked = Path(sys.argv[0]).name.lower() if sys.argv else ""
    if invoked == "schema-lens" and not _LEGACY_ALIAS_WARNED:
        typer.echo(
            "DEPRECATION: `schema-lens` alias is legacy. Use `solrguard`. "
            "Alias compatibility is planned until at least v0.5 and removal in a future major release.",
            err=True,
        )
        _LEGACY_ALIAS_WARNED = True
    return None


if __name__ == "__main__":
    app()
