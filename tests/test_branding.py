from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import schema_lens.cli as cli_mod
from schema_lens.cli import app


def test_cli_help_uses_solrguard_branding() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "SolrGuard" in result.stdout
    assert "schema-lens" in Path("pyproject.toml").read_text(encoding="utf-8")


def test_report_template_uses_solrguard_branding() -> None:
    template = Path("schema_lens/report/templates/report.html.j2").read_text(encoding="utf-8")
    assert "SolrGuard Report" in template


def test_legacy_alias_emits_deprecation_notice(monkeypatch, capsys) -> None:
    cli_mod._LEGACY_ALIAS_WARNED = False
    monkeypatch.setattr(cli_mod.sys, "argv", ["schema-lens", "run"])
    cli_mod.main()
    captured = capsys.readouterr()
    assert "DEPRECATION: `schema-lens` alias is legacy" in captured.err


def test_deprecation_schedule_docs_exist() -> None:
    assert Path("docs/deprecation-schedule.md").exists()
    assert Path("docs/major-version-module-migration.md").exists()
