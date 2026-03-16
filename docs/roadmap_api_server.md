# API Server Roadmap TODOs

## Security and Access

- [x] Add auth middleware with pluggable providers
- [x] Add RBAC role mapping for run/create/read/download operations
- [ ] Add per-user audit trail for job and artifact access
- [ ] Add API rate limiting and abuse protection

## Persistence and Scale

- [x] Introduce DB-backed job store (SQLite abstraction)
- [x] Add pull-worker mode for distributed worker readiness
- [ ] Add durable queue backend for distributed workers
- [ ] Add run cancellation and retry controls
- [ ] Add lease/heartbeat model for worker crash recovery

## UX and Integrations

- [ ] Add websocket/SSE live job progress
- [ ] Add dashboard-native API navigation for artifacts and summaries
- [ ] Add approval workflow APIs for governance promotions
- [ ] Add plugin-managed API route extensions
