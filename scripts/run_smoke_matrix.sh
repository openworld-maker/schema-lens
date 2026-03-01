#!/usr/bin/env bash
set -euo pipefail

RUN_ROOT="${1:-out/matrix}"
mkdir -p "$RUN_ROOT"

SCENARIOS=(
  "examples/changesets/no-changes.yaml no_changes"
  "examples/changesets/queryparams-only.yaml queryparams_only"
  "examples/changesets/json-input-queryjsonl.yaml json_inputs"
  "examples/changesets/fieldtype-change.yaml schema_ops"
)

for item in "${SCENARIOS[@]}"; do
  changeset=$(echo "$item" | awk '{print $1}')
  name=$(echo "$item" | awk '{print $2}')
  out_dir="$RUN_ROOT/$name"

  echo "== Running scenario: $name ($changeset)"
  .venv/bin/schema-lens validate "$changeset" --no-check-solr
  .venv/bin/schema-lens run "$changeset" --out "$out_dir"

  test -s "$out_dir/report.json"
  test -s "$out_dir/report.html"

  python3 - <<PY
import json
path = "$out_dir/report.json"
data = json.load(open(path))
summary = data.get("summary", {})
print("   summary:", summary)
if "queries_total" not in summary or summary["queries_total"] <= 0:
    raise SystemExit("queries_total missing or non-positive")
PY

done

echo "Smoke matrix completed: $RUN_ROOT"
