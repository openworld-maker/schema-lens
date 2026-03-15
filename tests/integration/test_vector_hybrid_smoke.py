import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_vector_hybrid_smoke():
    if os.getenv("RUN_SCHEMA_LENS_SMOKE") != "1":
        pytest.skip("Set RUN_SCHEMA_LENS_SMOKE=1 to run docker smoke test")

    repo = Path(__file__).resolve().parents[2]
    out_dir = repo / "out" / "integration_vector"

    setup = subprocess.run(
        [sys.executable, "scripts/setup_vector_demo.py"],
        cwd=repo,
        check=False,
    )
    assert setup.returncode == 0

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "schema_lens.cli",
            "run",
            "examples/changesets/vector-hybrid-demo.yaml",
            "--out",
            str(out_dir),
            "--enable-sensitivity",
        ],
        cwd=repo,
        check=False,
    )
    assert run.returncode == 0

    for rel in (
        "report.json",
        "report.html",
        "hybrid_sensitivity.json",
        "replay.json",
        "compare.json",
    ):
        path = out_dir / rel
        assert path.exists()
        assert path.stat().st_size > 0

    compare = json.loads((out_dir / "compare.json").read_text(encoding="utf-8"))
    vector_section = compare.get("vector_hybrid", {})
    assert vector_section.get("enabled") is True

    dominance = set()
    for payload in vector_section.get("hybrid_contribution", {}).values():
        for row in payload.get("per_query", []):
            dominance.add(row.get("dominance"))
    assert "vector_dominant" in dominance
    assert dominance <= {"lexical_dominant", "vector_dominant", "balanced"}

    sensitivity = json.loads((out_dir / "hybrid_sensitivity.json").read_text(encoding="utf-8"))
    assert sensitivity.get("enabled") is True
    assert any(
        scenario.get("queries_with_top1_flip", 0) >= 1
        for scenario in sensitivity.get("scenarios", [])
    )

    replay = json.loads((out_dir / "replay.json").read_text(encoding="utf-8"))
    scenarios = replay.get("vector_scenarios", {}).get("scenario_results", {})
    assert scenarios
    for payload in scenarios.values():
        for pair in payload.get("pairs", []):
            for target in ("baseline", "shadow"):
                meta = pair.get(target, {}).get("raw_response_meta", {})
                if pair.get(target, {}).get("skipped"):
                    continue
                assert "QTime" in meta
