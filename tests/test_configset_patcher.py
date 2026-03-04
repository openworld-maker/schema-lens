from pathlib import Path

from schema_lens.shadow.configset_patcher import apply_configset_updates, hash_directory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_configset_replace_mode(tmp_path):
    cfg = tmp_path / "cfg"
    _write(cfg / "conf/synonyms.txt", "old=>legacy\n")
    source = tmp_path / "syn_v2.txt"
    source.write_text("ss=>stainless steel\n", encoding="utf-8")

    changes = [
        {
            "op": "schema.synonym.update",
            "mode": "replace",
            "source_file": str(source),
            "target": {"files": [{"path": "conf/synonyms.txt"}]},
        }
    ]

    out = apply_configset_updates(configset_dir=cfg, changes=changes, changeset_path=None)
    assert out["applied"][0]["line_count_before"] == 1
    assert out["applied"][0]["line_count_after"] == 1
    assert (cfg / "conf/synonyms.txt").read_text(encoding="utf-8") == "ss=>stainless steel\n"


def test_configset_append_mode(tmp_path):
    cfg = tmp_path / "cfg"
    _write(cfg / "conf/stopwords.txt", "the\nand\n")
    source = tmp_path / "stop_v2.txt"
    source.write_text("for\nwith\n", encoding="utf-8")

    changes = [
        {
            "op": "schema.stopwords.update",
            "mode": "patch_append",
            "source_file": str(source),
            "target": {"files": [{"path": "conf/stopwords.txt"}]},
        }
    ]

    apply_configset_updates(configset_dir=cfg, changes=changes, changeset_path=None)
    assert (cfg / "conf/stopwords.txt").read_text(encoding="utf-8") == "the\nand\nfor\nwith\n"


def test_configset_merge_mode_is_deterministic(tmp_path):
    cfg = tmp_path / "cfg"
    _write(cfg / "conf/synonyms.txt", "ss=>steel\npipe,tube\n")
    source = tmp_path / "syn_v2.txt"
    source.write_text("pipe,tube\nss=>stainless steel\n", encoding="utf-8")

    changes = [
        {
            "op": "schema.synonym.update",
            "mode": "patch_merge",
            "source_file": str(source),
            "target": {"files": [{"path": "conf/synonyms.txt"}]},
        }
    ]

    apply_configset_updates(configset_dir=cfg, changes=changes, changeset_path=None)
    first_hash = hash_directory(cfg)

    apply_configset_updates(configset_dir=cfg, changes=changes, changeset_path=None)
    second_hash = hash_directory(cfg)

    lines = (cfg / "conf/synonyms.txt").read_text(encoding="utf-8").splitlines()
    assert lines == ["ss=>steel", "pipe,tube", "ss=>stainless steel"]
    assert first_hash == second_hash


def test_configset_target_path_handles_symlink_root(tmp_path):
    cfg_real = tmp_path / "cfg_real"
    _write(cfg_real / "conf/synonyms.txt", "old=>legacy\n")
    source = tmp_path / "syn_v2.txt"
    source.write_text("ss=>stainless steel\n", encoding="utf-8")

    cfg_link = tmp_path / "cfg_link"
    cfg_link.symlink_to(cfg_real, target_is_directory=True)

    changes = [
        {
            "op": "schema.synonym.update",
            "mode": "replace",
            "source_file": str(source),
            "target": {"files": [{"path": "conf/synonyms.txt"}]},
        }
    ]

    out = apply_configset_updates(configset_dir=cfg_link, changes=changes, changeset_path=None)
    assert out["applied"][0]["target_path"] == "conf/synonyms.txt"
