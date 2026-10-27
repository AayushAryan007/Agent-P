# AGENT-P — User Journeys

Status: Phase 1 baseline. Last updated: 2026-10-27. FR references point to [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md).

## J1 — Operator debugs a slow endpoint (flagship, MVP)

1. **Dashboard.** Operator signs in, sees recent runs and real metrics (FR-26), clicks **New task**.
2. **New Task.** Picks template *"Investigate slow endpoint"*, chooses the bundled repo `demo-slow-api` (or pastes a public GitHub URL), types the goal, keeps default limits (15 min, 40 LLM calls, 200k tokens). (FR-1, FR-2)
3. **Authorization review.** A panel lists exactly what the run may do: read files in the repo, search code, run tests and benchmark in a network-less container, propose a patch (requires approval). Operator clicks **Start run**. (FR-3)
4. **Live workspace.** The graph shows Coordinator → Repository Analysis → Debugging → Test & Verification → Review. Nodes change state as events arrive; the timeline scrolls; the narrative explains in plain language. (FR-20, FR-21)
5. **Inspect.** Operator clicks the Repository Analysis node → inspector shows tool calls (`list_tree`, `search_code`, `read_file`) with inputs and bounded outputs. (FR-22, FR-23)
6. **Retry observed.** Debugging agent's first structured output fails validation; the timeline shows `agent.output_invalid` → `retry.scheduled` → success. (FR-14)
7. **Approval.** Workflow pauses in `waiting_approval`; an approval card shows the diff and rationale. Operator approves. (FR-15)
8. **Verification.** Tests and benchmark run before and after the patch in the sandbox; real stdout excerpts and numbers appear. (FR-16)
9. **Report.** Results panel shows root cause, diff, test results, benchmark delta, evidence links, and the label **Verified**. (FR-25)

**Failure branches:** operator rejects patch → run completes `Not verified (rejected)`; tests fail after patch → `Not verified` with failing test list; budget exceeded → run `failed` with reason; operator cancels → `cancelled`, sandbox torn down.

## J2 — Viewer replays a completed run (MVP)

1. Visitor opens the public dashboard (no sign-in), sees past runs.
2. Opens a run → **Run details** with a "Recorded" banner.
3. Presses play at 2×; graph, timeline and inspector reconstruct state from stored events; scrubs back to the approval step. (FR-24)
4. Opens the report and follows an evidence link to the exact tool invocation that produced the benchmark number.

## J3 — Operator configures providers (MVP, minimal)

1. Opens **Settings** → sees Gemini `configured`, Groq `not configured` (key values never shown). (FR-31)
2. Sets default model and default run limits (stored server-side).

## J4 — Contributor adds a tool (P1, docs-level in MVP)

1. Reads ARCHITECTURE.md → implements a `Tool` with input/output Pydantic models and a permission scope.
2. Registers it in an agent's allowlist; writes a unit test using the tool test harness.

## J5 — Operator compares two runs (P1)

Select two runs of the same task with different models → side-by-side duration, tokens, verification result.
