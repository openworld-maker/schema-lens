#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/out/first_eval_$(date +%Y%m%d_%H%M%S)}"
CHANGESET_PATH="${CHANGESET_PATH:-$ROOT_DIR/examples/changesets/fieldtype-change.yaml}"
AUTO_BOOTSTRAP="${AUTO_BOOTSTRAP:-1}"

if [[ "${1:-}" == "--help" ]]; then
  cat <<USAGE
Usage: scripts/first_time_evaluator.sh [--no-bootstrap]

Runs one end-to-end local demo and prints key artifact links.

Environment overrides:
  OUT_DIR=<path>
  CHANGESET_PATH=<path>
  AUTO_BOOTSTRAP=0|1
USAGE
  exit 0
fi

if [[ "${1:-}" == "--no-bootstrap" ]]; then
  AUTO_BOOTSTRAP=0
fi

run_cmd() {
  if [[ -x "$ROOT_DIR/.venv/bin/solrguard" ]]; then
    "$ROOT_DIR/.venv/bin/solrguard" "$@"
  elif command -v solrguard >/dev/null 2>&1; then
    solrguard "$@"
  elif [[ -x "$ROOT_DIR/.venv/bin/schema-lens" ]]; then
    "$ROOT_DIR/.venv/bin/schema-lens" "$@"
  else
    echo "Error: neither solrguard nor schema-lens CLI found. Install with: pip install -e '.[dev]'" >&2
    exit 1
  fi
}

solr_up() {
  curl -fsS "http://localhost:8983/solr/admin/info/system?wt=json" >/dev/null 2>&1
}

if ! solr_up; then
  if [[ "$AUTO_BOOTSTRAP" == "1" ]]; then
    echo "[first-eval] Solr not detected; bootstrapping local demo cluster..."
    (cd "$ROOT_DIR" && make dev-up)
    for _ in $(seq 1 40); do
      if solr_up; then
        break
      fi
      sleep 2
    done
    if ! solr_up; then
      echo "Error: Solr did not become ready on http://localhost:8983" >&2
      exit 1
    fi
    (cd "$ROOT_DIR" && make demo-setup)
  else
    echo "Error: Solr not reachable on localhost:8983 and bootstrap disabled." >&2
    exit 1
  fi
fi

mkdir -p "$OUT_DIR"

echo "[first-eval] Running demo changeset: $CHANGESET_PATH"
run_cmd run "$CHANGESET_PATH" --out "$OUT_DIR"

report_html="$OUT_DIR/report.html"
report_json="$OUT_DIR/report.json"
compare_json="$OUT_DIR/compare.json"
manifest_json="$OUT_DIR/run_manifest.json"

echo
echo "[first-eval] Completed. Key artifacts:"
echo "- report.html: $report_html"
echo "- report.json: $report_json"
echo "- compare.json: $compare_json"
echo "- run_manifest.json: $manifest_json"
echo
echo "[first-eval] Browser links:"
echo "- file://$report_html"
echo "- file://$report_json"
