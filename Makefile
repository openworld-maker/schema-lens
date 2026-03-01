.PHONY: dev-up dev-down demo-setup smoke smoke-matrix lint test

dev-up:
	docker compose -f examples/solrcloud-docker/docker-compose.yml up -d

dev-down:
	docker compose -f examples/solrcloud-docker/docker-compose.yml down -v

demo-setup:
	curl -sS "http://localhost:8983/solr/admin/collections?action=CREATE&name=products&numShards=1&replicationFactor=1&collection.configName=_default&wt=json" || true
	curl -sS -X POST -H 'Content-Type: application/json' --data-binary @examples/docs.json "http://localhost:8983/solr/products/update?commit=true&wt=json"

lint:
	ruff check .

test:
	pytest -q

smoke:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/schema-lens run examples/changesets/fieldtype-change.yaml --out out/smoke
	test -s out/smoke/report.json
	test -s out/smoke/report.html

smoke-matrix:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	./scripts/run_smoke_matrix.sh out/matrix
