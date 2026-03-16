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


def test_first_time_evaluator_script_present_and_executable() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = repo / "scripts" / "first_time_evaluator.sh"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "run_cmd run" in text
    assert "report.html" in text
    assert script.stat().st_mode & 0o111
