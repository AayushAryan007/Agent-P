# AGENT-P — MVP Scope

Status: Phase 1 baseline. Last updated: 2026-10-27.

## In scope (P0)

| Area | Included | Notes |
|---|---|---|
| Workflow | One template: *Investigate slow endpoint → propose fix → verify* | Fixed DAG chosen by template; coordinator fills in subtask goals |
| Agents | Coordinator, Repository Analysis, Debugging, Test & Verification, Review | Clone, test parsing, diffing, benchmark parsing are deterministic functions |
| LLM | Gemini (free tier) via provider adapter | Groq adapter is the first P1 addition; see ADR-0002 |
| Orchestration | Custom asyncio state machine, in-process | See ADR-0001 |
| Repos | Bundled demo repo(s) + public GitHub HTTPS URLs (operator only) | See ADR-0003 |
| Tools | `list_tree`, `read_file`, `search_code`, `run_tests`, `run_benchmark`, `propose_patch`, `git_diff` | Typed, permissioned, bounded output |
| Sandbox | Docker container per execution step, hardened, network off during test runs | Colima locally, Linux Docker in prod |
| Approval | Human approval before patch application | Approve / reject with comment |
| Events | Persisted event log + SSE stream with catch-up | Versioned schema |
| UI | Dashboard, New Task, Live Workspace (2D graph), Run Details + Replay, Results, Settings (minimal) | 3D view deferred to M6 |
| Auth | Single admin token → httpOnly session; anonymous read-only | See ADR-0004 |
| Quality | pytest, vitest, ruff, mypy, tsc, GitHub Actions | One real-provider E2E test, gated by env |
| Deploy | Vercel (frontend), container host (backend + Postgres + sandbox) | Host chosen in Phase 2 |

## Deferred

**P1:** Groq/Ollama adapters, cost analytics, model comparisons, eval datasets & benchmarks dashboard, diff viewer enhancements, OpenTelemetry export, exportable traces, RAG over repo docs (only if justified), retry policy configuration UI.

**P2:** Workflow templates editor, true parallel scheduling across agents, resumable workflows after crash, model routing/fallback, plugins, multi-user + RBAC, SDK.

**Explicitly out:** arbitrary shell tool, private repo access, uploads of zip archives, agents modifying anything outside the sandbox copy, any network access from test execution.

## Milestones

| # | Milestone | Acceptance |
|---|---|---|
| M0 | Discovery + architecture docs | PRD, journeys, scope, ARCHITECTURE, TECH_STACK, DATABASE_DESIGN, API_SPECIFICATION, SECURITY_MODEL, ADRs committed |
| M1 | Backend foundation | `docker compose up` on Colima; `/healthz` and `/readyz`; Alembic migrations; append + SSE stream with `after_seq` catch-up, tested |
| M2 | Frontend shell | Tokens, app shell, Dashboard + New Task wired to real API, empty states |
| M3 | Real agents | Gemini adapter, tool registry, state machine; flagship run produces events shown in live 2D graph + inspector |
| M4 | Safe verification | Sandbox runner, approval gate, verification label computation, report |
| M5 | Replay, CI, deploy | Replay at variable speeds with zero LLM calls; GitHub Actions; Vercel + backend host live |
| M6 | Polish | 3D view, metrics, README, screenshots, demo video |
