# AGENT-P — Implementation Roadmap

Status: living document. Last updated: 2026-10-27. Milestones match [MVP_SCOPE.md](MVP_SCOPE.md).

Legend: ✅ done · 🔄 in progress · ⏳ next · ☐ not started

## M0 — Discovery and architecture ✅
- ✅ PRODUCT_REQUIREMENTS, USER_JOURNEYS, MVP_SCOPE
- ✅ ARCHITECTURE, TECH_STACK, DATABASE_DESIGN, API_SPECIFICATION, SECURITY_MODEL
- ✅ ADR-0001 … ADR-0007
- ✅ DESIGN_SYSTEM.md (Phase 3: tokens, components, screen specs)
- ✅ LLM models verified from official docs (TECH_STACK.md)

## M1 — Backend foundation ✅
- ✅ `backend/` with uv, ruff, mypy `--strict`, pytest; `app/config.py`; Dockerfile (non-root)
- ✅ `compose.yaml`: postgres (+ `agentp_test`), api; `.env.example` including `DOCKER_HOST`
- ✅ Colima bind mounts, `:ro`, `host.docker.internal`, `--network none` verified — results in LOCAL_DEVELOPMENT.md
- ✅ Alembic migration for all MVP tables; append-only trigger on `execution_events`; `alembic check` clean
- ✅ `/healthz`, `/readyz` (DB + migration head), request IDs, structlog with redaction, problem+json errors
- ✅ Event append (row lock + sequence + NOTIFY in-transaction), LISTEN broker, SSE with `Last-Event-ID` catch-up
- ✅ Auth (argon2 admin token, signed session, synchronizer CSRF), tasks, runs, cancel, metrics, meta, idempotency
- ✅ GitHub Actions CI: backend checks with Postgres service, frontend checks, image build
- ✅ **Accepted:** 26 tests cover concurrent ordered appends, append-only, NOTIFY only after commit, live SSE delivery < 1.5 s, resume without duplicates, CSRF/Origin, idempotency, visibility.
- Worker process deferred to M3 (it has nothing to execute before agents exist).

## M2 — Frontend shell 🔄

Done (built ahead of M1, against the API contract; shows honest offline/empty states until the backend exists):
- ✅ Vite + React 19 + TS strict, Tailwind v4 tokens, React Router, TanStack Query, `vercel.json`, `.env.example`
- ✅ App shell, Dashboard, Runs list, New Task (authorization summary), Settings (read-only), Run workspace (2D graph via React Flow + ELK, steps, timeline, inspector), replay player
- ✅ Event reducer shared by live view and replay, with unit tests (dedupe, retries, denied tools, unknown events)
- ✅ `/dev/preview` with an **ILLUSTRATIVE** fixture, excluded from production builds

- ✅ Wired to the real API (verified against the containerized backend); operator sign-in control; "no provider configured" notice

Remaining (lands with M3/M4 features):
- Approval card; results page
- Move ELK to its web-worker build to shrink the 1.6 MB workspace chunk

**Accept:** `npm run build` produces static `dist/` ✅; the dashboard shows the empty state with no runs ✅ and real values with runs (verified once M3 produces runs).

## M3 — Real agents ✅
- ✅ `LLMProvider` protocol, Gemini adapter (`generate_content`, forced function calling, thought signatures preserved), scripted provider for tests
- ✅ Tool gate (allowlist → schema → budget → timeout → redaction → record) with `list_tree`, `read_file`, `search_code`, `propose_patch`; path policy blocks traversal, absolute paths, `.git`, escaping symlinks
- ✅ Transition tables, DAG scheduler (baseline runs in parallel with planning/analysis), worker with SKIP LOCKED claim, DB-clock leases, cancellation, stale-run recovery, budgets
- ✅ Coordinator (plan + report), Repository Analysis, Debugging, Review agents; outputs via validated `submit_result`; invalid output → `agent.output_invalid` + retry
- ✅ `demo-repos/demo-slow-api`: N+1 in `list_orders()`; reference fix measured 273 ms → 8.5 ms p50 on the host
- ✅ Live workspace wired to SSE; approval card; cancel; report link
- ✅ **Accepted (2026-10-28, live Gemini):** run `01a17ec1…` on `demo-slow-api` — analysis located the N+1 at `app/repository.py:14`, the debugging agent proposed a batch query, operator approved, sandbox verification: 5/5 tests, p50 395.3 → 9.8 ms → **verified**. 17 LLM calls, ~59k tokens.
- Lessons from live runs (fixed): `gemini-3.8-flash` returned 503/504 under load → transient errors now fall back to `gemini-3.5-flash-lite` and stay there for the run; models mis-copied indentation into `propose_patch` → unique indentation-tolerant matching, clearer errors, and prompt guidance.

## M4 — Safe verification ✅
- ✅ Sandbox image `agentp-sandbox-python:0.1` (non-root, git, pytest/fastapi/httpx preinstalled) and runner (cap-drop ALL, no-new-privileges, read-only rootfs, tmpfs, pids/mem/cpu limits, timeout kill, labels + orphan cleanup)
- ✅ Clone (GitHub) and dependency install with network; tests/bench with `--network none`; original tests and benchmark restored before verification
- ✅ `propose_patch` validates by applying edits as text in memory (no code execution); patch applied only after approval
- ✅ Deterministic verification label rules; review agent; report artifact (narrative tagged model-written, results tagged recorded); results page
- ✅ **Accepted:** real-sandbox test run on the demo repo ends `verified` (394.8 → 9.1 ms p50 in a 1-CPU sandbox); rejection → `not_verified` with verify/review skipped; tests prove UID 10001, network blocked, read-only mounts, host secrets absent, timeout kill; protected-path rule covered by unit tests.
- Follow-ups: egress-restricted network for clone/install (see SECURITY_MODEL residual risks); gVisor on the production host.

## M5 — Replay, CI, deploy ☐
- Replay player (speeds, scrubbing) over the shared reducer; "Recorded" labeling
- GitHub Actions; Vercel project; OCI VM provisioning (rootless Docker, Caddy, backups)
- **Accept:** replay makes zero provider calls (asserted); the production demo completes the flagship run.

## M6 — Polish ☐
- 3D view (lazy-loaded R3F), metrics refinements, README, screenshots, demo video, contribution docs.
