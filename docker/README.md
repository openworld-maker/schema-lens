# Docker Image

Build:

```bash
docker build -f docker/Dockerfile -t schema-lens:local .
```

Run CLI:

```bash
docker run --rm -v "$PWD":/work -w /work schema-lens:local --help
```

Run API mode:

```bash
docker run --rm -p 8090:8090 -v "$PWD":/work -w /work schema-lens:local \
  api serve --out /work/out/api --host 0.0.0.0 --port 8090 --no-local-only
```
