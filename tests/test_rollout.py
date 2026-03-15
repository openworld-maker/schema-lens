from __future__ import annotations

from pathlib import Path

from schema_lens.rollout.alias_swap import build_alias_swap_plan
from schema_lens.rollout.canary import build_canary_plan
from schema_lens.rollout.gitops import compare_git_vs_live_configset
from schema_lens.rollout.rollback import build_rollback_plan
from schema_lens.rollout.verify import verify_post_cutover


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append((path, params))
        action = (params or {}).get("action")
        if action == "CLUSTERSTATUS":
            return {
                "cluster": {
                    "collections": {
                        "products": {"configName": "products_cfg"}
                    }
                }
            }
        raise AssertionError(f"Unexpected action: {action}")


def test_canary_plan_generation():
    plan = build_canary_plan(
        baseline_collection="products",
        canary_collection="products_canary",
        traffic_sample_ratio=0.2,
        replay_query_count=400,
        policy_bundle_paths=["a.yaml"],
    )
    assert plan["mode"] == "dry_run"
    assert plan["traffic_sample_ratio"] == 0.2


def test_alias_and_rollback_plan_generation():
    alias_plan = build_alias_swap_plan(
        alias="products_live",
        source_collection="products_v1",
        target_collection="products_v2",
    )
    rollback = build_rollback_plan(alias="products_live", previous_collection="products_v1")
    assert alias_plan["command"]["action"] == "CREATEALIAS"
    assert rollback["restore_collection"] == "products_v1"


def test_verify_post_cutover():
    result = verify_post_cutover(
        canary_compare={"summary": {"avg_overlap_ratio": 0.8}},
        prod_compare={"summary": {"avg_overlap_ratio": 0.75, "high_risk_percent": 3.0}},
        overlap_threshold=0.7,
        high_risk_threshold_pct=5.0,
    )
    assert result["pass"] is True


def test_git_drift_compare(monkeypatch, tmp_path: Path):
    local = tmp_path / "configset" / "conf"
    local.mkdir(parents=True)
    (local / "solrconfig.xml").write_text("<solrconfig />", encoding="utf-8")

    fake = _FakeClient()

    monkeypatch.setattr(
        "schema_lens.rollout.gitops.download_configset_archive",
        lambda client, name: b"zip-content",
    )

    result = compare_git_vs_live_configset(
        client=fake,
        collection="products",
        local_configset_dir=tmp_path / "configset",
    )
    assert result["collection"] == "products"
    assert "drift_detected" in result
