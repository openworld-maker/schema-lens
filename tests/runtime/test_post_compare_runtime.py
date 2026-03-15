from __future__ import annotations

import pytest

from schema_lens.runtime.post_compare_service import run_explain_flow


def test_run_explain_flow_adds_fallback_when_structured_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "schema_lens.runtime.post_compare_service.structured_explain_supported",
        lambda _caps: False,
    )
    monkeypatch.setattr(
        "schema_lens.runtime.post_compare_service.fetch_explains",
        lambda **_kwargs: [{"query_id": 1, "docs": []}],
    )

    bundles, fallback = run_explain_flow(
        eval_cfg={"explain": {"enabled": True, "structured": True}},
        compat_caps={},
        baseline_client=object(),
        baseline_collection="products",
        shadow_client=object(),
        shadow_name="products_shadow",
        replay_data={"pairs": []},
        compare_data={"diffs": []},
        effective_k=10,
    )

    assert bundles and bundles[0]["query_id"] == 1
    assert fallback is not None
    assert fallback["feature"] == "structured_explain"
