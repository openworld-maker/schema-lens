from pathlib import Path


def test_example_changesets_prefer_solrguard_version_key() -> None:
    repo = Path(__file__).resolve().parents[1]
    changesets_dir = repo / "examples" / "changesets"
    files = sorted(changesets_dir.glob("*.yaml"))
    assert files

    legacy_files = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "schema_lens_version:" in text:
            legacy_files.append(path.name)
        else:
            assert "solrguard_version:" in text, f"missing solrguard_version in {path.name}"

    assert legacy_files == ["legacy-schema-lens-version.yaml"]
