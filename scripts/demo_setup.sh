#!/usr/bin/env bash
set -euo pipefail

SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
COLLECTION="${COLLECTION:-products}"

curl -sS "${SOLR_URL}/admin/collections?action=CREATE&name=${COLLECTION}&numShards=1&replicationFactor=1&collection.configName=_default&wt=json" || true
curl -sS -X POST -H 'Content-Type: application/json' --data-binary @examples/docs.json "${SOLR_URL}/${COLLECTION}/update?commit=true&wt=json"

echo "Baseline setup complete for ${COLLECTION}"
