# Enterprise Deployment

## Recommended baseline

- run API mode in local-only or private network mode
- use pluggable auth provider/RBAC policy in API factory
- enable observability exporters and webhook notifications
- run policy gates in CI before promotion

## CI references

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `examples/deploy/github_actions.yml`
