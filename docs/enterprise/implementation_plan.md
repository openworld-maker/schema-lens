# Enterprise Evolution Implementation Plan

This plan maps the product shift to implementation tracks while preserving existing CLI/runtime behavior.

## Tier 1

1. Security/redaction defaults and audit trail hardening
2. Compatibility contract and capability detection

## Tier 2

3. Observability integrations (Prometheus, spans, webhooks)
4. Governance policy bundles + approvals + exceptions
5. GitOps rollout orchestration and post-cutover verify

## Tier 3

6. Segment-aware governance reporting
7. Privacy/retention controls and export-safe outputs
8. Packaging/deployment polish (Docker, Helm, CI release)

## Status

- Security: implemented (profiles, auth modes, redaction, audit artifacts)
- Compatibility: implemented and expanded with CLI detection commands
- Observability: implemented (events, prometheus output, webhook sink, OTEL-like span output)
- Governance: implemented (bundles, approvals, exceptions, promotion state, signing scaffold)
- Rollout: implemented (git drift, canary plan, alias swap dry-run/execute, rollback, verify)
- Segmentation: implemented (grouping + segment policy checks)
- Privacy: implemented (maskers, profiles, retention, export-safe mode)
- Packaging: implemented baseline (Docker, Helm, release workflow checks)

## Current deltas in this cycle

- Added explicit compatibility contract docs + CLI (`detect-capabilities`, `compatibility`)
- Added enterprise docs index and migration messaging to governance framing
