# AGENT-P — Technology Stack

Status: Phase 2 baseline. Last updated: 2026-10-27. Versions are pinned in lockfiles when each package is added; this document records the choice and its reasoning.

## Frontend (fixed: Vite + React + TypeScript, hosted on Vercel)

| Concern | Choice | Why / trade-off |
|---|---|---|
| Build | Vite, TypeScript `strict` | Fixed decision; static `dist/` |
| Routing | React Router (data router) | Standard, works with Vercel SPA rewrite |
| Styling | Tailwind CSS v4 + CSS custom-property design tokens | Tokens live in one CSS file, so the theme is easy to audit; Tailwind keeps components consistent without a heavy UI kit |
| Primitives | Radix UI primitives (dialog, tabs, tooltip, popover) | Accessibility (focus, keyboard) solved; unstyled, so it doesn't fight the design |
| Icons | lucide-react | Consistent stroke icons matching the references |
| Server state | TanStack Query | Caching, refetch, pagination for REST |
| Live run state | Zustand store fed by a pure `reduceEvent` function | One reducer for live view and replay; easy to unit test |
| 2D graph | React Flow (`@xyflow/react`) + ELK.js layered layout | Custom React nodes (status, timers), pan/zoom, keyboard selection; ELK handles DAG layout better than dagre for ports/edges |
| 3D graph (M6) | React Three Fiber + drei | Fixed decision; lazy-loaded so it doesn't bloat the main bundle |
| Diff view | `react-diff-view` + `diff` parsing | Proper file-by-file split/unified views |
| Code highlight | Shiki (lazy) | Accurate highlighting for tool outputs and diffs |
| Timeline virtualization | TanStack Virtual | NFR-7: thousands of events |
| Fonts | Inter (UI), JetBrains Mono (code/ids) | Clean, readable; matches references' style |
| Tests | Vitest + Testing Library; Playwright (M5) for E2E | Fast unit tests for the reducer and components |
| Lint/format | ESLint (typescript-eslint) + Prettier | Standard |

## Backend

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 (containers); managed by **uv** | uv gives fast lockfile-based installs and fetches 3.12 even though the host has 3.11 |
| Web | FastAPI + Uvicorn | Required; OpenAPI out of the box |
| Validation | Pydantic v2, pydantic-settings | Required; also defines tool and agent I/O schemas |
| DB access | SQLAlchemy 2.0 async + asyncpg | Typed ORM; asyncpg supports LISTEN/NOTIFY |
| Migrations | Alembic | Required |
| Streaming | SSE via `sse-starlette` | One-way stream, native browser reconnect with `Last-Event-ID`, works through proxies; see ADR-0005 |
| Queue / fan-out | PostgreSQL `SKIP LOCKED` + `LISTEN/NOTIFY` | No extra infrastructure; see ADR-0006 |
| LLM | `google-genai` SDK (Gemini) behind `LLMProvider`; Groq adapter in P1 | ADR-0002. Model IDs come from config, validated against the provider's model list at startup |
| Sandbox | Docker SDK for Python (`docker`), engine selected by `DOCKER_HOST` | Same code on Colima and on the Linux host |
| HTTP client | httpx | Async; used for GitHub metadata checks |
| Auth | argon2-cffi (token hash), itsdangerous (signed session cookie) | ADR-0004 |
| Logging | structlog (JSON in prod, pretty in dev) | Structured, with context vars for correlation IDs |
| Tests | pytest, pytest-asyncio, httpx `AsyncClient`; DB tests against Compose Postgres | Real Postgres needed for SKIP LOCKED / NOTIFY behavior |
| Quality | ruff (lint + format), mypy `--strict` on `app/`, import-linter | — |
| Observability (P1) | OpenTelemetry SDK + OTLP exporter | Deferred until MVP works |

## Infrastructure

| Concern | Choice |
|---|---|
| Local containers | **Colima** + docker CLI + `docker compose` plugin (no Docker Desktop) |
| Backend host | **OCI Always Free Ampere A1** VM, Ubuntu 24.04 arm64, **rootless Docker**, Caddy for TLS — ADR-0007 |
| Sandbox runtime hardening | `runc` with hardened flags (MVP); gVisor `runsc` on the OCI host when available (arm64 supported) |
| Frontend hosting | Vercel, root `frontend/`, Vite preset, SPA rewrite |
| CI | GitHub Actions: backend lint/type/test (with a Postgres service), frontend lint/type/test/build |
| Images | Multi-arch where possible; the sandbox image `agentp-sandbox-python` built for arm64 + amd64 |

## Not used (and why)

- **Redis**: Postgres covers the queue, notifications, and idempotency at our scale. Revisit for multi-instance rate limiting.
- **Celery / message broker**: one worker process with an asyncio scheduler is enough; SKIP LOCKED gives safe claiming.
- **Vector DB / RAG**: no proven need. Repository navigation uses `search_code` (ripgrep-style) and file reads. Revisit in P1 with evidence.
- **LangGraph**: ADR-0001.
- **WebSockets**: no client→server streaming needed; ADR-0005.

## To verify at integration time

- Current Gemini free-tier model IDs, rate limits, function-calling + JSON-schema support → recorded here in Phase 5.
- Groq models with reliable tool calling (P1).
- gVisor availability on the provisioned OCI image.
