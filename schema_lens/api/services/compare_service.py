"""Environment compare service orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.api.models import ApiJob
from schema_lens.api.schemas.run_requests import CompareEnvRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.env_compare.runner import compare_environments
from schema_lens.report.html_report import render_html_report
from schema_lens.report.json_report import build_report_json
from schema_lens.util.io import ensure_dir, write_json, write_text


class CompareService:
    def __init__(self, storage: ApiStorage) -> None:
        self.storage = storage

    def execute(self, job: ApiJob) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = CompareEnvRequest(**job.request_payload)
        env1 = Path(payload.env1 or payload.env1_path or "").resolve()
        env2 = Path(payload.env2 or payload.env2_path or "").resolve()
        queries_path = Path(payload.queries_path).resolve()
        out_dir = Path(payload.out_dir).resolve() if payload.out_dir else self.storage.run_dir(job.job_id)
        ensure_dir(out_dir)

        options = payload.options if isinstance(payload.options, dict) else {}
        query_format = str(options.get("query_format", payload.query_format))
        k_value = int(options.get("k", payload.k))
        max_queries = options.get("max_queries", payload.max_queries)
        verbose = bool(options.get("verbose", payload.verbose))

        result = compare_environments(
            env1_path=env1,
            env2_path=env2,
            queries_path=queries_path,
            query_format=query_format,
            k=k_value,
            max_queries=max_queries if isinstance(max_queries, int) or max_queries is None else None,
            verbose=verbose,
        )

        write_json(out_dir / "replay.json", result["replay"])
        write_json(out_dir / "compare.json", result["compare"])
        report_data = build_report_json(
            manifest={
                "run_id": job.job_id,
                "inputs": {"env1": str(env1), "env2": str(env2), "queries": str(queries_path)},
                "outputs": {"out_dir": str(out_dir.resolve())},
                "settings": {"mode": "compare_env"},
            },
            compare_data=result["compare"],
            replay_data=result["replay"],
        )
        write_json(out_dir / "report.json", report_data)
        template_dir = Path(__file__).resolve().parents[2] / "report" / "templates"
        write_text(out_dir / "report.html", render_html_report(report_data, template_dir))

        artifacts = self.storage.list_artifacts_from_dir(out_dir)
        manifest_paths = {item["name"]: item["path"] for item in artifacts}
        self.storage.save_artifact_manifest(
            job.job_id,
            {"job_id": job.job_id, "artifacts_dir": str(out_dir), "paths": manifest_paths},
        )
        outputs = {
            "artifacts_dir": str(out_dir.resolve()),
            "compare_json": str((out_dir / "compare.json").resolve()),
            "report_json": str((out_dir / "report.json").resolve()),
            "report_html": str((out_dir / "report.html").resolve()),
            "artifacts": artifacts,
        }
        metadata = {
            "summary": result.get("compare", {}).get("summary", {})
            if isinstance(result.get("compare"), dict)
            else {},
            "compatibility": result.get("compare", {}).get("compatibility", {})
            if isinstance(result.get("compare"), dict)
            else {},
        }
        return outputs, metadata
