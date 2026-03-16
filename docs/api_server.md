# API Server

`solrguard` provides a FastAPI-based service mode for run orchestration and artifact access.

## Architecture Overview

- API layer: `schema_lens/api/app.py`, `schema_lens/api/routes/*`
- Service layer: `schema_lens/api/services/*`
- Job manager: `schema_lens/api/jobs.py`
- File persistence: `schema_lens/api/storage.py`
- Schemas: `schema_lens/api/schemas/*`

The API calls existing core engine code (`schema_lens.cli.run`, compare-env runner, gate evaluator) instead of duplicating behavior.

## Endpoint List

- `GET /health`
- `GET /health/details`
- `GET /capabilities`
- `GET /plugins`
- `POST /runs`
- `GET /runs`
- `GET /runs/{job_id}`
- `GET /runs/{job_id}/summary`
- `POST /compare-env`
- `GET /compare-env/{job_id}`
- `POST /gates`
- `GET /gates/{job_id}`
- `GET /artifacts/{job_id}`
- `GET /artifacts/{job_id}/{artifact_name}`
- Compatibility:
  - `POST /gate`
  - `GET /runs/{job_id}/artifacts`
  - `GET /runs/{job_id}/artifacts/{artifact_name}`

## Request/Response Examples

Start server:

```bash
solrguard api serve --data-dir .solrguard_api --host 127.0.0.1 --port 8080
```

SQLite-backed job metadata:

```bash
solrguard api serve \
  --data-dir .solrguard_api \
  --job-store sqlite \
  --sqlite-path .solrguard_api/jobs.db
```

External worker readiness (API queues, separate worker drains):

```bash
solrguard api serve --worker-mode external
```

Create run:

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H "Content-Type: application/json" \
  -d @examples/api/create_run_from_path.json
```

Check status:

```bash
curl -sS http://127.0.0.1:8080/runs/<job_id>
```

List artifacts:

```bash
curl -sS http://127.0.0.1:8080/artifacts/<job_id>
```

Download report:

```bash
curl -sS http://127.0.0.1:8080/artifacts/<job_id>/report.json
```

## Local Dev

- Run service: `solrguard api serve --data-dir .solrguard_api`
- Inspect config/storage: `solrguard api inspect --data-dir .solrguard_api --job-store sqlite --sqlite-path .solrguard_api/jobs.db`
- OpenAPI docs: `http://127.0.0.1:8080/docs`

## Storage Model

By default:

```text
.solrguard_api/
  jobs/
    <job_id>/
      job.json
      request.json
      artifacts.json
  runs/
    <job_id>/
      report.json
      report.html
      compare.json
      ...
  logs/
```

The API stores references to artifact paths; artifacts remain owned by run output directories.
Job metadata can be stored in:

- `file` backend (`jobs/<job_id>/job.json`)
- `sqlite` backend (`jobs.db`)

## Security Notes

- Local-only binding is enforced by middleware when enabled.
- Pluggable auth provider and RBAC policy hooks are supported in `create_api_app(...)`.
- API audit events are written to `logs/api_audit.jsonl` (method/path/status/principal/roles/outcome).
- API request snapshots redact obvious secret keys (`token`, `password`, `secret`, `auth`, etc.).
- Artifact access is constrained to tracked artifacts for each job.

## Future Extension Points

- plugin inventory available via `/plugins`.
- external worker mode can be promoted to distributed queue workers.
- DB backend abstraction can be extended to Postgres-backed multi-node scheduling.

## Follow-up Tasks

1. OIDC/JWT provider integration for auth middleware
2. Postgres-backed job store with migrations
3. Distributed worker execution with leasing/heartbeats
4. Websocket/live progress streaming
5. Run cancellation
6. Dashboard UI integration
7. Approval workflow integration
8. Plugin-managed API extensions
9. Multi-user audit support
10. Rate limiting / abuse protection
