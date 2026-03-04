import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_rewrite_diff_smoke():
    if os.getenv("RUN_SCHEMA_LENS_SMOKE") != "1":
        pytest.skip("Set RUN_SCHEMA_LENS_SMOKE=1 to run docker smoke test")

    repo = Path(__file__).resolve().parents[2]
    out_dir = repo / "out" / "integration_rewrite"

    setup = subprocess.run(
        [sys.executable, "scripts/setup_procurement_demo.py"],
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
            "examples/changesets/procurement-synonym-rewrite.yaml",
            "--out",
            str(out_dir),
        ],
        cwd=repo,
        check=False,
    )
    assert run.returncode == 0

    compare_path = out_dir / "compare.json"
    assert compare_path.exists()
    compare_data = json.loads(compare_path.read_text(encoding="utf-8"))

    rewrite = compare_data.get("rewrite_diff", {})
    assert rewrite.get("enabled") is True
    flags = {
        flag
        for row in rewrite.get("per_query", [])
        for flag in row.get("risk_flags", [])
    }
    assert "SYNONYM_EXPANSION_CHANGED" in flags
