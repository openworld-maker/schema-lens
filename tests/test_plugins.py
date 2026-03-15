from __future__ import annotations

from pathlib import Path

import pytest

from schema_lens.plugins.base import BasePlugin, PluginMetadata
from schema_lens.plugins.errors import PluginIssue
from schema_lens.plugins.loader import (
    PluginRuntimeConfig,
    _version_satisfies,
    load_plugin_runtime_config,
    load_plugins,
    validate_issues,
)
from schema_lens.plugins.registry import PluginRegistry


def _write_plugin(path: Path, *, name: str, version_req: str = "*") -> None:
    path.write_text(
        "\n".join(
            [
                "from schema_lens.plugins.base import BasePlugin, PluginMetadata",
                "",
                "class P(BasePlugin):",
                "    metadata = PluginMetadata(",
                f"        name='{name}',",
                "        version='0.1.0',",
                "        plugin_type='gate',",
                f"        schema_lens_version='{version_req}',",
                "    )",
                "",
                "PLUGIN = P",
            ]
        ),
        encoding="utf-8",
    )


def test_plugin_registry_register_and_resolve() -> None:
    class P(BasePlugin):
        metadata = PluginMetadata(name="a", version="0.1", plugin_type="gate")

    registry = PluginRegistry()
    registry.register(P())
    selection = registry.resolve(enable=None, disable=[])
    assert [p.metadata.name for p in selection.plugins] == ["a"]


def test_load_plugins_from_local_path(tmp_path: Path) -> None:
    plugin_file = tmp_path / "sample.py"
    _write_plugin(plugin_file, name="local_one")

    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, plugin_paths=[str(plugin_file)]),
        base_dir=tmp_path,
    )

    assert not loaded.issues
    assert [p.metadata.name for p in loaded.active] == ["local_one"]


def test_load_plugins_failure_isolated(tmp_path: Path) -> None:
    _write_plugin(tmp_path / "good.py", name="good")
    (tmp_path / "bad.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, plugin_paths=[str(tmp_path)]),
        base_dir=tmp_path,
    )

    assert [p.metadata.name for p in loaded.active] == ["good"]
    assert any(issue.stage == "load" for issue in loaded.issues)


def test_load_plugins_entry_points(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class EP:
        name = "ep_plugin"

        @staticmethod
        def load():
            class P(BasePlugin):
                metadata = PluginMetadata(name="ep_plugin", version="0.1", plugin_type="gate")

            return P

    class EPs(list):
        def select(self, *, group: str):
            assert group == "schema_lens.plugins"
            return self

    monkeypatch.setattr("importlib.metadata.entry_points", lambda: EPs([EP()]))

    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, plugin_paths=[]),
        base_dir=tmp_path,
    )

    assert not loaded.issues
    assert [p.metadata.name for p in loaded.active] == ["ep_plugin"]


def test_compatibility_check_filters_plugins(tmp_path: Path) -> None:
    plugin_file = tmp_path / "future.py"
    _write_plugin(plugin_file, name="future_only", version_req=">=99.0.0")

    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, plugin_paths=[str(plugin_file)]),
        base_dir=tmp_path,
    )

    assert loaded.active == []
    assert any(issue.stage == "compatibility" for issue in loaded.issues)


def test_validate_issues_strict_raises() -> None:
    loaded_issue = PluginIssue(plugin="x", stage="load", message="broken", fatal=True)
    with pytest.raises(Exception, match="plugin runtime blocked"):
        validate_issues([loaded_issue], strict=True)


def test_load_plugin_runtime_config_from_changeset_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "plugins.yaml"
    config_path.write_text(
        "enabled: true\nstrict: true\npaths:\n  - ./plugins\n",
        encoding="utf-8",
    )
    changeset = {
        "plugins": {
            "config": str(config_path),
            "strict": False,
        }
    }
    cfg = load_plugin_runtime_config(changeset, tmp_path / "changeset.yaml")
    assert cfg.enabled is True
    assert cfg.strict is False
    assert cfg.plugin_paths == ["./plugins"]


def test_version_parser_supports_ranges() -> None:
    assert _version_satisfies("1.2.3", ">=1.0.0,<2.0.0")
    assert not _version_satisfies("2.2.0", "<2.0.0")
