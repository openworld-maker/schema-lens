"""Environment compare route."""

from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, Request

from schema_lens.api.models import CompareEnvRequest
from schema_lens.api.storage import ApiStorage
from schema_lens.env_compare.runner import compare_environments
from schema_lens.util.io import ensure_dir, write_json

router = APIRouter(tags=["compare-env"])


@router.post("/compare-env")
def compare_env(payload: CompareEnvRequest, request: Request) -> dict[str, object]:
    storage: ApiStorage = request.app.state.storage
    out_dir = Path(payload.out_dir).resolve() if payload.out_dir else storage.base_dir / "compare_env" / str(uuid.uuid4())
    ensure_dir(out_dir)

    result = compare_environments(
        env1_path=Path(payload.env1_path),
        env2_path=Path(payload.env2_path),
        queries_path=Path(payload.queries_path),
        query_format=payload.query_format,
        k=payload.k,
        max_queries=payload.max_queries,
        verbose=payload.verbose,
    )
    write_json(out_dir / "replay.json", result["replay"])
    write_json(out_dir / "compare.json", result["compare"])

    return {
        "out_dir": str(out_dir.resolve()),
        "outputs": {
            "replay_json": str((out_dir / "replay.json").resolve()),
            "compare_json": str((out_dir / "compare.json").resolve()),
        },
        "compare": result["compare"],
    }
