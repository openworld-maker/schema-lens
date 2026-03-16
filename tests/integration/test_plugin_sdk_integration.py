from __future__ import annotations

import logging
from pathlib import Path

import pytest

from schema_lens.plugins.contracts.gate import GateResult
from schema_lens.plugins.loader import PluginRuntimeConfig, load_plugins
from schema_lens.report.json_report import build_report_json
from schema_lens.runtime.data_query_service import load_or_extract_queries
from schema_lens.runtime.plugin_service import initialize_plugins


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_query_source_plugin_loads_queries() -> None:
    root = _repo_root()
    loaded = load_plugins(
        PluginRuntimeConfig(
            enabled=True,
            directories=[str(root / "examples/plugins")],
            enabled_plugins=["sample_query_source"],
            enable_entry_points=False,
        ),
        base_dir=root,
    )
    plugin = next(p for p in loaded.active if p.metadata.name == "sample_query_source")
    query_cases = load_or_extract_queries(
        query_source_type="plugin",
        queries_source={"provider": "sample_query_source"},
        queries_path=root / "examples/queries.txt",
        query_cfg={},
        outputs={"queries_extracted_jsonl": str(root / "out" / "tmp_queries.jsonl")},
        manifest_inputs={},
        manifest_settings={},
        persist_sensitive_effective=False,
        query_source_plugins=[plugin],
        plugin_source_config={"path": "examples/querylogs/procurement_queries_custom.json"},
        plugin_context={"changeset_path": str(root / "examples/changesets/plugin-sdk-demo.yaml")},
    )
    assert query_cases
    assert query_cases[0].params is not None
    assert query_cases[0].params.get("q")


def test_gate_plugin_custom_result_appears() -> None:
    root = _repo_root()
    loaded = load_plugins(
        PluginRuntimeConfig(
            enabled=True,
            directories=[str(root / "examples/plugins/sample_gate")],
            enabled_plugins=["sample_gate"],
            enable_entry_points=False,
        ),
        base_dir=root,
    )
    gate = loaded.active[0]
    result = gate.evaluate(  # type: ignore[attr-defined]
        {"overlap_threshold": 0.5, "failure_pct": 30},
        {"compare_data": {"diffs": [{"jaccard": 0.2}, {"jaccard": 0.8}, {"jaccard": 0.3}]}},
    )
    assert isinstance(result, GateResult)
    assert result.stats is not None
    assert result.stats["evaluated"] == 3
    assert result.passed is False


def test_report_plugin_section_in_report_json() -> None:
    root = _repo_root()
    loaded = load_plugins(
        PluginRuntimeConfig(
            enabled=True,
            directories=[str(root / "examples/plugins/sample_report")],
            enabled_plugins=["sample_report"],
            enable_entry_points=False,
        ),
        base_dir=root,
    )
    report_plugin = loaded.active[0]
    section = report_plugin.render_json_section(  # type: ignore[attr-defined]
        {"plugin_config": {"group_by": "tenant"}},
        {
            "replay_data": {
                "pairs": [
                    {"query": {"segment": {"tenant": "a"}}},
                    {"query": {"segment": {"tenant": "a"}}},
                    {"query": {"segment": {"tenant": "b"}}},
                ]
            }
        },
    )
    report = build_report_json(
        manifest={},
        compare_data={"summary": {}},
        replay_data={},
        plugin_report_sections={"json": [{"plugin": "sample_report", "section": section}], "html": []},
    )
    assert report["plugin_report_sections"]["json"][0]["section"]["counts"]["a"] == 2


def test_broken_plugin_non_strict_completes_with_warning(tmp_path: Path) -> None:
    broken_dir = tmp_path / "plugins"
    broken_dir.mkdir()
    (broken_dir / "broken.py").write_text("raise RuntimeError('broken import')\n", encoding="utf-8")

    runtime = initialize_plugins(
        changeset_raw={
            "plugins": {
                "enabled": True,
                "strict_mode": False,
                "directories": [str(broken_dir)],
                "enabled_plugins": [],
                "entry_points": False,
            }
        },
        changeset_path=tmp_path / "changeset.yaml",
        run_id="r1",
        out_dir=tmp_path,
        manifest_payload={},
        logger=logging.getLogger("test"),
    )
    assert runtime.enabled is True
    assert runtime.issues


def test_broken_plugin_strict_mode_fails(tmp_path: Path) -> None:
    broken_dir = tmp_path / "plugins"
    broken_dir.mkdir()
    (broken_dir / "broken.py").write_text("raise RuntimeError('broken import')\n", encoding="utf-8")

    with pytest.raises(Exception, match="plugin runtime blocked"):
        initialize_plugins(
            changeset_raw={
                "plugins": {
                    "enabled": True,
                    "strict_mode": True,
                    "directories": [str(broken_dir)],
                    "enabled_plugins": [],
                    "entry_points": False,
                }
            },
            changeset_path=tmp_path / "changeset.yaml",
            run_id="r1",
            out_dir=tmp_path,
            manifest_payload={},
            logger=logging.getLogger("test"),
        )
