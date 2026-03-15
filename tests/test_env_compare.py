from pathlib import Path

from schema_lens.env_compare.diff import build_environment_compare
from schema_lens.env_compare.models import EnvironmentConfig
from schema_lens.env_compare.runner import _client_for_env, load_env_config


def test_load_env_config_and_auth_header(monkeypatch, tmp_path: Path):
    cfg_path = tmp_path / "env.yaml"
    cfg_path.write_text(
        """
name: prod_us
solr_url: http://localhost:8983/solr
collection: products
auth:
  type: basic
  username: user
  password: pass
headers:
  X-Test: yes
""",
        encoding="utf-8",
    )
    config = load_env_config(cfg_path)
    assert config.name == "prod_us"

    captured = {}

    class DummyClient:
        def __init__(self, solr_url, headers=None, cert=None, verify=True, verbose=False):
            captured["solr_url"] = solr_url
            captured["headers"] = headers or {}
            captured["cert"] = cert
            captured["verify"] = verify

    monkeypatch.setattr("schema_lens.env_compare.runner.SolrHttpClient", DummyClient)
    _client_for_env(config, verbose=False)
    assert captured["solr_url"] == "http://localhost:8983/solr"
    assert captured["headers"]["Authorization"].startswith("Basic ")
    assert captured["headers"]["X-Test"] == "True"


def test_build_environment_compare_summary():
    replay_data = {
        "k": 10,
        "pairs": [
            {
                "query": {"params": {"q": "bolt"}},
                "baseline": {"docs": [{"id": "A", "rank": 1}, {"id": "B", "rank": 2}]},
                "shadow": {"docs": [{"id": "C", "rank": 1}, {"id": "B", "rank": 2}]},
            }
        ],
    }
    compare = build_environment_compare(
        replay_data,
        10,
        EnvironmentConfig("env1", "u1", "c1").to_dict(),
        EnvironmentConfig("env2", "u2", "c2").to_dict(),
    )
    summary = compare["environment_compare"]["summary"]
    assert summary["top1_mismatch_percent"] == 100.0
    assert "top10_overlap_lt_0_7_percent" in summary
