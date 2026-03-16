from __future__ import annotations

import pytest

from schema_lens.api.schemas.run_requests import CompareEnvRequest, GateRequest, RunCreateRequest


def test_run_request_requires_exactly_one_changeset_source() -> None:
    with pytest.raises(Exception):
        RunCreateRequest()
    with pytest.raises(Exception):
        RunCreateRequest(changeset_path="a.yaml", changeset={"baseline": {}})
    req = RunCreateRequest(changeset_path="a.yaml")
    assert req.changeset_path == "a.yaml"


def test_compare_env_request_accepts_env_aliases() -> None:
    req = CompareEnvRequest(env1="a.yaml", env2="b.yaml", queries_path="q.jsonl")
    assert req.env1 == "a.yaml"
    req2 = CompareEnvRequest(env1_path="a.yaml", env2_path="b.yaml", queries_path="q.jsonl")
    assert req2.env1_path == "a.yaml"


def test_gate_request_accepts_compare_aliases() -> None:
    req = GateRequest(compare_artifact="compare.json", policy_path="policy.yaml")
    assert req.compare_artifact == "compare.json"
    req2 = GateRequest(compare_path="compare.json", policy_path="policy.yaml")
    assert req2.compare_path == "compare.json"

