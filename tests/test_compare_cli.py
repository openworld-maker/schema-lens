from pathlib import Path

from typer.testing import CliRunner

from schema_lens.cli import app


def test_compare_command_works_with_demo_replay_fixture(tmp_path: Path) -> None:
    runner = CliRunner()
    replay = Path("examples/demo/replay_minimal.json")
    out = tmp_path / "compare.json"

    result = runner.invoke(app, ["compare", "--replay", str(replay), "--out", str(out)])

    assert result.exit_code == 0, result.stdout
    assert out.exists()
