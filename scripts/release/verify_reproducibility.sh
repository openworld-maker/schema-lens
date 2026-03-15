#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

if [[ ! -f "$DIST_DIR/SHA256SUMS.txt" ]]; then
  echo "missing $DIST_DIR/SHA256SUMS.txt"
  exit 1
fi

( cd "$DIST_DIR" && shasum -a 256 -c SHA256SUMS.txt )
