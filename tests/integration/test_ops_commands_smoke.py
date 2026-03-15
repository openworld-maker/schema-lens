import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http_json(url: str, timeout_seconds: float = 20.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2.0) as response:  # noqa: S310
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _run(repo: Path, argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=repo, check=False, capture_output=True, text=True)


def _ensure_demo_setup(repo: Path) -> None:
    dev_up = _run(repo, ["make", "dev-up"])
    assert dev_up.returncode == 0, dev_up.stderr

    demo_setup = _run(repo, ["make", "demo-setup"])
    assert demo_setup.returncode == 0, demo_setup.stderr


@pytest.mark.integration
def test_compare_env_monitor_serve_smoke():
    if os.getenv("RUN_SCHEMA_LENS_SMOKE") != "1":
        pytest.skip("Set RUN_SCHEMA_LENS_SMOKE=1 to run docker smoke test")

    repo = Path(__file__).resolve().parents[2]
    _ensure_demo_setup(repo)

    out_root = repo / "out" / "integration_ops"
    compare_out = out_root / "env_compare"
    run_out = out_root / "run"
    monitor_out = out_root / "monitor"
    env1 = out_root / "env1.yaml"
    env2 = out_root / "env2.yaml"
    out_root.mkdir(parents=True, exist_ok=True)

    env1.write_text(
        "\n".join(
            [
                'name: "local_a"',
                'solr_url: "http://localhost:8983/solr"',
                'collection: "products"',
                "request_defaults:",
                '  defType: "edismax"',
                '  rows: 10',
                '  fl: "id,score"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env2.write_text(
        "\n".join(
            [
                'name: "local_b"',
                'solr_url: "http://localhost:8983/solr"',
                'collection: "products"',
                "request_defaults:",
                '  defType: "edismax"',
                '  rows: 10',
                '  fl: "id,score"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    compare_proc = _run(
        repo,
        [
            sys.executable,
            "-m",
            "schema_lens.cli",
            "compare-env",
            "--env1",
            str(env1),
            "--env2",
            str(env2),
            "--queries",
            "examples/queries/env_compare_queries.jsonl",
            "--out",
            str(compare_out),
        ],
    )
    assert compare_proc.returncode == 0, compare_proc.stderr
    for rel in ("replay.json", "compare.json", "env_compare.json", "report.json", "report.html"):
        path = compare_out / rel
        assert path.exists()
        assert path.stat().st_size > 0

    compare_payload = json.loads((compare_out / "compare.json").read_text(encoding="utf-8"))
    env_section = compare_payload.get("environment_compare", {})
    assert env_section.get("enabled") is True
    assert "summary" in env_section

    run_proc = _run(
        repo,
        [
            sys.executable,
            "-m",
            "schema_lens.cli",
            "run",
            "examples/changesets/fieldtype-change.yaml",
            "--out",
            str(run_out),
        ],
    )
    assert run_proc.returncode == 0, run_proc.stderr
    assert (run_out / "report.json").exists()

    monitor_proc = _run(
        repo,
        [
            sys.executable,
            "-m",
            "schema_lens.cli",
            "monitor",
            "--baseline-snapshot",
            str(run_out),
            "--queries",
            "examples/queries/env_compare_queries.jsonl",
            "--out",
            str(monitor_out),
        ],
    )
    assert monitor_proc.returncode == 0, monitor_proc.stderr
    assert (monitor_out / "latest_monitor.json").exists()
    assert (monitor_out / "monitor_history.jsonl").exists()

    latest_monitor = json.loads((monitor_out / "latest_monitor.json").read_text(encoding="utf-8"))
    assert latest_monitor.get("enabled") is True

    port = _free_port()
    serve_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "schema_lens.cli",
            "serve",
            "--run",
            str(run_out),
            "--port",
            str(port),
        ],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        overview = _wait_for_http_json(f"http://127.0.0.1:{port}/api/overview")
        assert isinstance(overview, dict)
        assert "report.json" in overview
    finally:
        serve_proc.terminate()
        try:
            serve_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            serve_proc.kill()
            serve_proc.wait(timeout=5)
