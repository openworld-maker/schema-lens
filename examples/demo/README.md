# Offline Demo Dataset

This demo lets you try SolrGuard without a live Solr cluster.

## Run in under 3 minutes

```bash
mkdir -p out/demo_offline
solrguard compare --replay examples/demo/replay_minimal.json --out out/demo_offline/compare.json
solrguard report --compare out/demo_offline/compare.json --manifest examples/demo/run_manifest_minimal.json --replay examples/demo/replay_minimal.json --out out/demo_offline
solrguard gate --compare out/demo_offline/compare.json --policy examples/policy/gate_default.yaml || true
```

Outputs:

- `out/demo_offline/compare.json`
- `out/demo_offline/report.json`
- `out/demo_offline/report.html`

## Dataset files

- `queries.jsonl`: demo query cases
- `baseline_config.yaml`: illustrative baseline settings
- `candidate_config.yaml`: illustrative candidate settings
- `replay_minimal.json`: replay payload consumed by `solrguard compare`
- `run_manifest_minimal.json`: minimal manifest consumed by `solrguard report`
- `expected/`: expected outputs generated from this fixture
