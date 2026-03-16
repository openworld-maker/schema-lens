# Docker Image

Build:

```bash
docker build -f docker/Dockerfile -t solrguard:local .
```

Run CLI:

```bash
docker run --rm -v "$PWD":/work -w /work solrguard:local --help
```

Run API mode:

```bash
docker run --rm -p 8090:8090 -v "$PWD":/work -w /work solrguard:local \
  api serve --out /work/out/api --host 0.0.0.0 --port 8090 --no-local-only
```
