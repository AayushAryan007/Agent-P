# AGENT-P — Product Requirements

Status: **Phase 1 (Discovery) — accepted baseline**. Last updated: 2026-10-27.
Related: [MVP_SCOPE.md](MVP_SCOPE.md), [USER_JOURNEYS.md](USER_JOURNEYS.md), [ARCHITECTURE_DECISIONS/](ARCHITECTURE_DECISIONS/).

## 1. Product brief

AGENT-P is an execution and observability environment for real AI agent workflows. A user submits an engineering task against a Python repository. A coordinator decomposes it, specialized agents call typed and permission-checked tools, code runs only in an isolated sandbox, and every step is persisted as an ordered execution event. The UI — live graph, inspector, timeline, replay, and final report — is a projection of that event log.

**Core principle:** make complex AI workflows understandable, observable, reproducible, and controllable. Nothing on screen is decorative; every status and metric is derived from recorded data.

## 2. Users

| Persona | Need | Primary screens |
|---|---|---|
| **Operator** (the admin; initially the project author) — backend/AI engineer running agent tasks | Start a debugging task, watch it, approve or reject patches, trust the verification result | New Task, Live Workspace, Results |
| **Viewer** (anonymous visitor, reviewer, recruiter, mentor) | Understand what an agent run did, inspect evidence, replay it | Dashboard, Run Details/Replay, Results |
| **Contributor** (open-source developer) | Add a tool, agent, or provider without understanding the whole system | Docs, code module boundaries |

## 3. Problem

Agent systems today are opaque. Chat-style UIs hide intermediate steps; tracing tools (LangSmith, Langfuse, Phoenix) show LLM spans but not workflow semantics — dependencies, blocked agents, approval gates, or whether a claimed fix was actually verified. Agents also routinely *claim* success ("tests pass") without evidence.

## 4. Differentiators

1. **Evidence-backed verification labels.** `Verified` / `Partially verified` / `Not verified` are computed from sandbox exit codes and parsed test/benchmark output, never from model text.
2. **Workflow-level visualization** of dependencies, states, and hand-offs — not just a span tree.
3. **Human approval gate** before any patch is applied, recorded in the audit trail.
4. **Deterministic replay** from persisted events; the LLM is never re-invoked to reconstruct a run.
5. **Security-first tool execution**: a model's tool request is a proposal, not an authorization.

## 5. Functional requirements (MVP)

IDs are referenced from MVP_SCOPE and acceptance tests.

### Tasks and runs
- **FR-1** The operator can create a task: natural-language goal, workflow template, repository source, model, execution limits.
- **FR-2** Repository source is either a bundled demo repo or a public `https://github.com/<owner>/<repo>` URL (operator only; see FR-30).
- **FR-3** Before starting, the UI displays the exact tools, permissions, limits, and model the run is authorized to use.
- **FR-4** The operator can start, and cancel, a run. A task may have multiple runs.
- **FR-5** Runs, agent runs, tool invocations, approvals, artifacts and events are persisted and listable after completion.

### Execution
- **FR-10** A coordinator produces a structured plan (DAG of agent steps) for the selected template.
- **FR-11** Agents: Coordinator, Repository Analysis, Debugging, Test & Verification, Review. Deterministic steps (clone, test run parsing, diff) are plain functions, not agents.
- **FR-12** Agents call only the tools in their allowlist; every call is validated (schema + permission + limits) before execution and recorded.
- **FR-13** Agent states: `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`. Transitions are validated by the state machine.
- **FR-14** Failed tool calls and invalid model outputs are retried within a bounded policy; each retry is a recorded event.
- **FR-15** A proposed patch requires explicit operator approval before it is applied to the sandbox working copy. Rejection ends the run with a report marked `Not verified`.
- **FR-16** Verification runs the repository's tests (and a benchmark when the template defines one) before and after the patch in an isolated container.
- **FR-17** Runs enforce budgets: max wall time, max LLM calls, max tokens, max tool calls. Exceeding a budget fails the run with a clear reason.

### Observability and UI
- **FR-20** Events stream to the browser in real time; a reconnecting client receives all missed events in order.
- **FR-21** Live workspace: 2D agent graph, run status panel, event timeline, agent inspector, tool-call detail, narrative, results panel.
- **FR-22** Agent inspector shows role, status, timestamps, inputs, outputs, tool calls, errors, token usage, duration.
- **FR-23** Tool invocation detail shows sanitized inputs, bounded output summary, status, duration, trace ID.
- **FR-24** Replay plays stored events at 0.5×–8× speed with scrubbing; replay UI is visibly labeled "Recorded".
- **FR-25** Final report: problem summary, root cause, patch, file-by-file diff, test results, benchmark results, evidence links, limitations, next steps, verification label.
- **FR-26** Dashboard metrics (success rate, average duration, tokens, failures) are computed from stored runs; empty states are shown when there is no data.

### Access
- **FR-30** Single admin (operator) authenticates with a token configured in backend env; anonymous users have read-only access to runs marked public.
- **FR-31** Provider configuration (keys, default model, timeouts) is backend-only. Settings UI shows which providers are configured, never key values.

## 6. Non-functional requirements

| ID | Requirement | MVP target |
|---|---|---|
| NFR-1 | Event delivery latency (persist → browser) | p95 < 500 ms on the demo host |
| NFR-2 | Reconnect recovery | No lost or duplicated events in the rendered state after reconnect (dedupe by `sequence_number`) |
| NFR-3 | Run duration for flagship demo | < 5 min typical, hard cap 15 min |
| NFR-4 | Concurrency | 1 active run on the public demo (configurable); queue additional runs |
| NFR-5 | Durability | Events committed before being streamed; API restart marks in-flight runs `failed` with reason `interrupted` (resume is P2) |
| NFR-6 | Accessibility | WCAG AA contrast; every graph action reachable via keyboard; 2D graph is the accessible primary view |
| NFR-7 | Frontend performance | Workspace stays interactive at 2,000 events per run (virtualized timeline) |
| NFR-8 | Cost | Default to free-tier providers; per-run token budget; zero cost when idle |
| NFR-9 | Portability | Same sandbox code runs on Colima (local) and a Linux Docker host (prod), driven by `DOCKER_HOST` |
| NFR-10 | Code quality | Typed (mypy/tsc strict), linted (ruff/eslint), tested (pytest/vitest), CI on every push |

## 7. Security and privacy requirements (summary — detail in SECURITY_MODEL.md, Phase 2)

- Untrusted code runs only in sandbox containers: non-root, `--cap-drop=ALL`, `no-new-privileges`, no network during test execution, CPU/memory/pids/time limits, read-only base with a size-limited writable workdir.
- Docker socket is never mounted into a sandbox. API talks to the engine via `DOCKER_HOST`.
- Repository clone happens in a dedicated step with network enabled but no secrets; size and file-count limits; GitHub HTTPS URLs only; no submodules or LFS.
- Repository contents and tool outputs are untrusted data: they are delimited in prompts, never interpreted as instructions to the platform, and cannot widen tool permissions.
- File tools are confined to the run workspace (resolved-path check, no symlink escape).
- Secrets never reach the browser, logs, events, or sandbox env. Event payloads pass through a redaction filter.
- Auth on all mutating endpoints; rate limits on task creation; audit log for approvals, cancellations, and config changes.
- Retention: sandbox workspaces deleted at run end; repos and artifacts deleted after a configurable period (default 7 days); events retained.

## 8. Acceptance criteria (MVP Definition of Done)

The MVP is accepted when, on the deployed demo, a user can:

1. Open the app and see a dashboard with real (or explicitly empty) metrics.
2. Create a task against the bundled slow-API repo and start a run.
3. Watch agents progress in the live graph driven by real backend events.
4. Click an agent and a tool call and see real inputs/outputs.
5. See a failure or retry rendered when one occurs (covered by a fault-injection test as well).
6. Review the proposed diff and approve or reject it.
7. See tests and benchmark executed in the sandbox with real output.
8. See a verification label consistent with the actual exit codes and benchmark numbers.
9. Reopen the run after completion and replay it without any LLM call (asserted by test: zero provider calls during replay).
10. Understand what happened from the report and timeline alone.

And the codebase has automated tests for: state transitions, event persistence and ordering, reconnect catch-up, tool permission enforcement, path confinement, authorization, budget enforcement, and verification-label computation.

## 9. Risks, assumptions, unknowns

| Risk | Impact | Mitigation |
|---|---|---|
| Free-tier models produce invalid tool calls / JSON | Runs fail or stall | Strict schemas, validate-and-repair retry (bounded), recorded attempts; Groq adapter as fallback |
| Free-tier rate limits during demo | Demo fails publicly | 1 concurrent run, budget caps, clear "rate limited" state, recorded showcase runs available for replay |
| Gemini free tier may use prompts for product improvement | Privacy | Only public/demo code is ever sent; documented in SECURITY_MODEL |
| Sandbox escape or abuse via public repo URL | Host compromise | Operator-only URL runs, hardened containers, network off during execution, documented residual risk; gVisor (`runsc`) on prod host as hardening step |
| Public repo has heavy/odd dependencies | Tests cannot run | Support `requirements.txt`/`pyproject` with pip only, install timeout, result marked `Not verified` with reason |
| UI built ahead of real data drifts into fake dashboards | Credibility | Backend event schema first; no hardcoded metrics; "illustrative" label for any design fixture |

**Assumptions:** single operator; English tasks; Python 3.11+ target repos; demo host has a real Docker engine.

**Open (Phase 2):** backend host choice, exact Gemini/Groq models, benchmark harness format.
