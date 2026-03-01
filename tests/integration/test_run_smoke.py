import os
import subprocess

import pytest


@pytest.mark.integration
def test_run_smoke_make_target():
    if os.getenv("RUN_SCHEMA_LENS_SMOKE") != "1":
        pytest.skip("Set RUN_SCHEMA_LENS_SMOKE=1 to run docker smoke test")

    proc = subprocess.run(["make", "smoke"], check=False)
    assert proc.returncode == 0
