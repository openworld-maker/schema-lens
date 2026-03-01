#!/usr/bin/env bash
set -euo pipefail

RUN_ROOT="${1:-out/matrix}"
mkdir -p "$RUN_ROOT"

SCENARIOS=(
  "examples/changesets/no-changes.yaml no_changes"
  "examples/changesets/queryparams-only.yaml queryparams_only"
  "examples/changesets/json-input-queryjsonl.yaml json_inputs"
  "examples/changesets/fieldtype-change.yaml schema_ops"
  "examples/changesets/prod_realism_example.yaml prod_realism"
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
  test -s "$out_dir/schema_risk.json"

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

tmp_gate_pass="$RUN_ROOT/gate_pass.yaml"
cat > "$tmp_gate_pass" <<'YAML'
version: 1
fail:
  - metric: "avg_overlap"
    op: "<"
    value: 0.0
YAML

.venv/bin/schema-lens gate --compare "$RUN_ROOT/no_changes/compare.json" --policy "$tmp_gate_pass"

tmp_gate_fail="$RUN_ROOT/gate_fail.yaml"
cat > "$tmp_gate_fail" <<'YAML'
version: 1
fail:
  - metric: "avg_overlap"
    op: ">"
    value: -1
YAML

set +e
.venv/bin/schema-lens gate --compare "$RUN_ROOT/no_changes/compare.json" --policy "$tmp_gate_fail"
gate_rc=$?
set -e
if [[ "$gate_rc" -ne 2 ]]; then
  echo "expected gate fail exit code 2, got $gate_rc"
  exit 1
fi

echo "Smoke matrix completed: $RUN_ROOT"
