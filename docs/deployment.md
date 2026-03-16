# Deployment

## Docker

- Dockerfile: `docker/Dockerfile`
- guide: `docker/README.md`
- example: `examples/deploy/docker_run.md`

## Helm

- chart: `helm/solrguard`
- values: `helm/solrguard/values.yaml`

## API service

```bash
solrguard api serve --data-dir .solrguard_api --host 127.0.0.1 --port 8080
```

With SQLite-backed jobs and external workers:

```bash
solrguard api serve --job-store sqlite --sqlite-path .solrguard_api/jobs.db --worker-mode external
```
