#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
SBOM_DIR="$ROOT_DIR/dist/sbom"

mkdir -p "$DIST_DIR" "$SBOM_DIR"

python -m pip install --upgrade build >/dev/null
python -m build

if command -v syft >/dev/null 2>&1; then
  syft "$ROOT_DIR" -o cyclonedx-json > "$SBOM_DIR/schema-lens.sbom.cdx.json"
else
  echo '{"note":"syft not installed; SBOM generation skipped"}' > "$SBOM_DIR/schema-lens.sbom.cdx.json"
fi

shasum -a 256 "$DIST_DIR"/* > "$DIST_DIR/SHA256SUMS.txt"

echo "Release artifacts ready in $DIST_DIR"
