from pathlib import Path


def test_docs_surface_assets_and_workflow_present() -> None:
    repo = Path(__file__).resolve().parents[1]

    roadmap = repo / "docs" / "roadmap.md"
    assert roadmap.exists()
    assert "## Available now" in roadmap.read_text(encoding="utf-8")

    outputs = repo / "docs" / "example-outputs.md"
    outputs_text = outputs.read_text(encoding="utf-8")
    assert "report_html_thumb.png" in outputs_text
    assert "report_json_thumb.png" in outputs_text

    assert (repo / "docs" / "assets" / "report_html_thumb.png").exists()
    assert (repo / "docs" / "assets" / "report_json_thumb.png").exists()

    workflow = repo / ".github" / "workflows" / "docs-links.yml"
    assert workflow.exists()
    assert "lychee" in workflow.read_text(encoding="utf-8").lower()

    examples_index = repo / "docs" / "examples.md"
    assert examples_index.exists()
    assert "3-minute offline demo" in examples_index.read_text(encoding="utf-8").lower()
    security_doc = repo / "docs" / "security.md"
    assert security_doc.exists()
    assert "follow-up tasks" in security_doc.read_text(encoding="utf-8").lower()
    security_roadmap = repo / "docs" / "roadmap_security.md"
    assert security_roadmap.exists()
    compat_doc = repo / "docs" / "solr_compatibility.md"
    assert compat_doc.exists()
    assert "follow-up tasks" in compat_doc.read_text(encoding="utf-8").lower()
    compat_roadmap = repo / "docs" / "roadmap_compatibility.md"
    assert compat_roadmap.exists()
    api_server_doc = repo / "docs" / "api_server.md"
    api_text = api_server_doc.read_text(encoding="utf-8")
    assert "## Follow-up Tasks" in api_text
    assert "### Next 3 Most Important Production Features" in api_text


def test_first_time_evaluator_script_present_and_executable() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = repo / "scripts" / "first_time_evaluator.sh"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "run_cmd run" in text
    assert "report.html" in text
    assert script.stat().st_mode & 0o111


def test_demo_dataset_files_exist() -> None:
    repo = Path(__file__).resolve().parents[1]
    demo = repo / "examples" / "demo"
    for rel in (
        "README.md",
        "queries.jsonl",
        "baseline_config.yaml",
        "candidate_config.yaml",
        "replay_minimal.json",
        "run_manifest_minimal.json",
        "expected/compare.json",
        "expected/report.json",
    ):
        assert (demo / rel).exists(), f"missing demo file: {rel}"
