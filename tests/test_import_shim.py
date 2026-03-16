from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import solrguard
from solrguard.cli import app


def test_solrguard_import_shim_exposes_version_and_cli() -> None:
    assert isinstance(solrguard.__version__, str)
    assert app is not None
