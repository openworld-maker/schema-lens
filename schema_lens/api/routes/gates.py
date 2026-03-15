"""Gate evaluation route."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from schema_lens.api.models import GateRequest
from schema_lens.compare.gate import evaluate_gate, load_gate_policy
from schema_lens.util.io import read_json

router = APIRouter(tags=["gates"])


@router.post("/gate")
def gate(payload: GateRequest) -> dict[str, object]:
    compare_data = read_json(Path(payload.compare_path))
    policy_path = Path(payload.policy_path)
    policy_data = load_gate_policy(policy_path)
    result = evaluate_gate(compare_data=compare_data, policy_data=policy_data, policy_dir=policy_path.parent.resolve())
    return result
