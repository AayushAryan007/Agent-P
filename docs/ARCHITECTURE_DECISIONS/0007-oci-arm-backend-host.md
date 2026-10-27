# ADR-0007: OCI Always Free Ampere A1 VM as backend host

- Status: Accepted
- Date: 2026-10-27

## Context

The backend needs long-running processes, PostgreSQL, persistent SSE connections, and a real Docker engine to launch sandbox containers. Budget is zero. Development happens on an arm64 Mac with Colima.

## Options

| | OCI Always Free A1 | Paid VPS | Railway/Render (+ Fly sandbox) |
|---|---|---|---|
| Cost | Free (up to 4 OCPU / 24 GB) | ~$5–10/mo | Free tiers are limited; sandbox needs another service |
| Docker engine for sandboxes | Yes | Yes | No (on Railway/Render) |
| Arch | arm64 (same as dev) | Usually amd64 | amd64 |
| Ops burden | Ours: OS, TLS, backups, updates | Same | Lower for the API, higher overall |
| Risk | Free capacity can be scarce in some regions; idle reclamation policy for free instances | Low | Split architecture |

## Decision

OCI A1, Ubuntu 24.04 arm64, rootless Docker, Docker Compose deployment, Caddy for automatic TLS, nightly `pg_dump` to OCI Object Storage. Images are built multi-arch in CI. The design stays portable to "any Linux host with Docker", so moving to a paid VPS is a configuration change.

## Consequences

- + Free, a real engine, and the same CPU architecture as local development.
- − We own patching, firewalling (only 80/443 open; SSH restricted by key and IP), and monitoring (an external uptime check on `/healthz`).
- Requires a domain (or a free subdomain service) for TLS and cross-site cookies — to be decided before M5.
