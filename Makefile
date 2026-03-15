.PHONY: dev-up dev-down demo-setup demo-setup-procurement demo-setup-vector smoke smoke-vector smoke-matrix lint test

dev-up:
	docker compose -f examples/solrcloud-docker/docker-compose.yml up -d

dev-down:
	docker compose -f examples/solrcloud-docker/docker-compose.yml down -v

demo-setup:
	curl -sS "http://localhost:8983/solr/admin/collections?action=CREATE&name=products&numShards=1&replicationFactor=1&collection.configName=_default&wt=json" || true
	curl -sS -X POST -H 'Content-Type: application/json' --data-binary @examples/docs.json "http://localhost:8983/solr/products/update?commit=true&wt=json"

demo-setup-procurement:
	@if [ -x .venv/bin/python ]; then \
		.venv/bin/python scripts/setup_procurement_demo.py; \
	else \
		python3 scripts/setup_procurement_demo.py; \
	fi

demo-setup-vector:
	@if [ -x .venv/bin/python ]; then \
		.venv/bin/python scripts/setup_vector_demo.py; \
	else \
		python3 scripts/setup_vector_demo.py; \
	fi

lint:
	ruff check .

test:
	pytest -q

smoke:
	$(MAKE) dev-up
	/bin/zsh -lc 'for i in $$(seq 1 40); do curl -fsS "http://localhost:8983/solr/admin/info/system?wt=json" >/dev/null && break; sleep 2; done'
	$(MAKE) demo-setup
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/schema-lens run examples/changesets/fieldtype-change.yaml --out out/smoke
	test -s out/smoke/report.json
	test -s out/smoke/report.html

smoke-vector:
	$(MAKE) dev-up
	/bin/zsh -lc 'for i in $$(seq 1 40); do curl -fsS "http://localhost:8983/solr/admin/info/system?wt=json" >/dev/null && break; sleep 2; done'
	$(MAKE) demo-setup-vector
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/schema-lens run examples/changesets/vector-hybrid-demo.yaml --out out/smoke_vector
	test -s out/smoke_vector/report.json
	test -s out/smoke_vector/report.html
	test -s out/smoke_vector/hybrid_sensitivity.json

smoke-matrix:
	$(MAKE) dev-up
	/bin/zsh -lc 'for i in $$(seq 1 40); do curl -fsS "http://localhost:8983/solr/admin/info/system?wt=json" >/dev/null && break; sleep 2; done'
	$(MAKE) demo-setup
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	./scripts/run_smoke_matrix.sh out/matrix
