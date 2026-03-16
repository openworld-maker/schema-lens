from __future__ import annotations

import logging
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
from schema_lens.runtime.plugin_service import execute_plugins, plugin_artifact_paths


def _write_plugin(path: Path, *, name: str, version_req: str = "*", plugin_type: str = "gate") -> None:
    path.write_text(
        "\n".join(
            [
                "from schema_lens.plugins.base import BasePlugin, PluginMetadata",
                "",
                "class P(BasePlugin):",
                "    metadata = PluginMetadata(",
                f"        name='{name}',",
                "        version='0.1.0',",
                f"        plugin_type='{plugin_type}',",
                f"        compatible_schema_lens_version='{version_req}',",
                "    )",
                "",
                "PLUGIN = P",
            ]
        ),
        encoding="utf-8",
    )


def test_plugin_metadata_backward_compat_alias() -> None:
    metadata = PluginMetadata(
        name="a",
        version="0.1.0",
        plugin_type="gate",
        schema_lens_version=">=0.1.0",
    )
    assert metadata.compatible_schema_lens_version == ">=0.1.0"


def test_plugin_registry_register_lookup_and_list() -> None:
    class P(BasePlugin):
        metadata = PluginMetadata(name="a", version="0.1", plugin_type="gate", description="x")

    registry = PluginRegistry()
    registry.register(P())

    assert registry.get_by_name("a") is not None
    assert [item.metadata.name for item in registry.get_by_type("gate")] == ["a"]
    assert registry.list_plugins()[0]["description"] == "x"


def test_plugin_registry_compatibility_validation() -> None:
    class P(BasePlugin):
        metadata = PluginMetadata(
            name="future",
            version="0.1",
            plugin_type="gate",
            compatible_schema_lens_version=">=99.0.0",
        )

    registry = PluginRegistry()
    registry.register(P())
    assert registry.validate_plugin_compatibility("0.1.2") == ["future"]


def test_load_plugins_from_builtin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called = {"value": False}

    def _register(registry: PluginRegistry) -> None:
        called["value"] = True

        class P(BasePlugin):
            metadata = PluginMetadata(name="builtin_one", version="0.1", plugin_type="gate")

        registry.register(P())

    monkeypatch.setattr("schema_lens.plugins.loader._load_builtin_plugins", lambda registry: (_register(registry), [])[1])
    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, load_builtin=True, enable_entry_points=False),
        base_dir=tmp_path,
    )
    assert called["value"] is True
    assert [p.metadata.name for p in loaded.active] == ["builtin_one"]


def test_load_plugins_from_local_directory(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    _write_plugin(plugin_dir / "sample.py", name="local_one")

    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, directories=[str(plugin_dir)], enable_entry_points=False),
        base_dir=tmp_path,
    )

    assert not loaded.issues
    assert [p.metadata.name for p in loaded.active] == ["local_one"]


def test_strict_mode_validation_behavior() -> None:
    issue = PluginIssue(plugin="x", stage="load", message="broken", fatal=True)
    validate_issues([issue], strict=False)
    with pytest.raises(Exception, match="plugin runtime blocked"):
        validate_issues([issue], strict=True)


def test_compatibility_check_filters_plugins(tmp_path: Path) -> None:
    plugin_file = tmp_path / "future.py"
    _write_plugin(plugin_file, name="future_only", version_req=">=99.0.0")

    loaded = load_plugins(
        PluginRuntimeConfig(enabled=True, directories=[str(plugin_file)], enable_entry_points=False),
        base_dir=tmp_path,
    )

    assert loaded.active == []
    assert any(issue.stage == "compatibility" for issue in loaded.issues)


def test_plugin_exception_isolation_non_strict(tmp_path: Path) -> None:
    class BoomPlugin(BasePlugin):
        metadata = PluginMetadata(name="boom", version="0.1", plugin_type="analyzer")

        def execute(self, context, payload):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    runtime = type(
        "Runtime",
        (),
            {
                "active_plugins": [BoomPlugin()],
                "strict": False,
                "plugin_configs": {},
                "results": [],
                "issues": [],
                "manifest": type(
                    "Manifest",
                    (),
                    {"output_artifacts": {}, "failed_plugins": [], "warnings": [], "loaded_plugins": []},
                )(),
                "enabled": True,
            },
    )()
    result = execute_plugins(
        runtime=runtime,
        run_id="r1",
        out_dir=tmp_path,
        changeset_path=tmp_path / "changeset.yaml",
        changeset_raw={},
        manifest_payload={},
        compare_data={},
        replay_data={},
        logger=logging.getLogger("test"),
    )
    assert result["enabled"] is True
    assert result["results"][0]["status"] == "error"
    assert result["issues"][0]["plugin"] == "boom"


def test_plugin_runtime_config_parsing_new_and_legacy_keys(tmp_path: Path) -> None:
    cfg_path = tmp_path / "plugins.yaml"
    cfg_path.write_text(
        (
            "enabled: true\n"
            "strict_mode: true\n"
            "directories:\n"
            "  - ./plugins\n"
            "enabled_plugins:\n"
            "  - sample\n"
            "config:\n"
            "  sample:\n"
            "    threshold: 2\n"
        ),
        encoding="utf-8",
    )
    changeset = {"plugins": {"config": str(cfg_path), "strict_mode": False}}
    cfg = load_plugin_runtime_config(changeset, tmp_path / "changeset.yaml")
    assert cfg.enabled is True
    assert cfg.strict_mode is False
    assert cfg.directories == [str((tmp_path / "plugins").resolve())]
    assert cfg.enabled_plugins == ["sample"]
    assert cfg.config["sample"]["threshold"] == 2


def test_artifact_path_generation(tmp_path: Path) -> None:
    paths = plugin_artifact_paths(tmp_path, "sample_gate")
    assert paths.root.exists()
    assert paths.result_json.name == "result.json"
    assert paths.debug_json.name == "debug.json"
    assert paths.notes_txt.name == "notes.txt"


def test_version_parser_supports_ranges() -> None:
    assert _version_satisfies("1.2.3", ">=1.0.0,<2.0.0")
    assert not _version_satisfies("2.2.0", "<2.0.0")
