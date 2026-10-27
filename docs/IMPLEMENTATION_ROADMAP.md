# AGENT-P — Implementation Roadmap

Status: living document. Last updated: 2026-10-27. Milestones match [MVP_SCOPE.md](MVP_SCOPE.md).

Legend: ✅ done · 🔄 in progress · ⏳ next · ☐ not started

## M0 — Discovery and architecture ✅
- ✅ PRODUCT_REQUIREMENTS, USER_JOURNEYS, MVP_SCOPE
- ✅ ARCHITECTURE, TECH_STACK, DATABASE_DESIGN, API_SPECIFICATION, SECURITY_MODEL
- ✅ ADR-0001 … ADR-0007
- ✅ DESIGN_SYSTEM.md (Phase 3: tokens, components, screen specs)
- ✅ LLM models verified from official docs (TECH_STACK.md)

## M1 — Backend foundation ☐
- `backend/` with uv, ruff, mypy, pytest; `app/config.py`
- `compose.yaml`: postgres, api, worker (Colima); `.env.example` including `DOCKER_HOST`
- Verify Colima bind-mount read/write and `host.docker.internal` (record the results)
- Alembic migrations for all MVP tables; append-only grants on `execution_events`
- `/healthz`, `/readyz`, request ID middleware, structlog, problem+json errors
- Event append service (row lock + sequence + NOTIFY) and SSE streamer with catch-up
- **Accept:** tests prove ordered persistence under concurrent appends, catch-up from `after_seq`, no duplicates after reconnect, NOTIFY only after commit.

## M2 — Frontend shell 🔄

Done (built ahead of M1, against the API contract; shows honest offline/empty states until the backend exists):
- ✅ Vite + React 19 + TS strict, Tailwind v4 tokens, React Router, TanStack Query, `vercel.json`, `.env.example`
- ✅ App shell, Dashboard, Runs list, New Task (authorization summary), Settings (read-only), Run workspace (2D graph via React Flow + ELK, steps, timeline, inspector), replay player
- ✅ Event reducer shared by live view and replay, with unit tests (dedupe, retries, denied tools, unknown events)
- ✅ `/dev/preview` with an **ILLUSTRATIVE** fixture, excluded from production builds

Remaining:
- Wire to the real API once M1 lands; sign-in UI; approval card; results page
- Move ELK to its web-worker build to shrink the 1.6 MB workspace chunk
- `frontend/` Vite + React + TS strict; Tailwind tokens; router; `vercel.json` rewrite; `.env.example`
- App shell (sidebar, top bar), Dashboard and New Task wired to the real API; loading/empty/error states
- **Accept:** `npm run build` produces static `dist/`; the dashboard shows the empty state with no runs and real values with runs.

## M3 — Real agents ☐
- `LLMProvider` + Gemini adapter (verify models and limits from official docs; record them in TECH_STACK)
- Tool registry and gate; `list_tree`, `read_file`, `search_code`
- State machine transitions + scheduler + worker claim loop + budgets + cancellation
- Coordinator, Repository Analysis, Debugging agents with structured outputs
- `demo-repos/demo-slow-api` (FastAPI + SQLite N+1 bug, pytest suite, benchmark script)
- Live workspace: 2D graph (React Flow), inspector, timeline, tool detail
- **Accept:** a real run against the demo repo shows each step and tool call live; an injected invalid output shows a retry.

## M4 — Safe verification ☐
- Sandbox image and runner; clone/install/test/bench steps with the hardening flags
- `propose_patch` with dry-run apply; approval gate API + UI
- Verification label rules, review agent, final report
- **Accept:** approve → `verified` on the demo repo; reject → `not_verified (rejected)`; a patch editing tests is capped at `partially_verified`; sandbox network is proven off by a test.

## M5 — Replay, CI, deploy ☐
- Replay player (speeds, scrubbing) over the shared reducer; "Recorded" labeling
- GitHub Actions; Vercel project; OCI VM provisioning (rootless Docker, Caddy, backups)
- **Accept:** replay makes zero provider calls (asserted); the production demo completes the flagship run.

## M6 — Polish ☐
- 3D view (lazy-loaded R3F), metrics refinements, README, screenshots, demo video, contribution docs.
