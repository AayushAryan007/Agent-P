# AGENT-P — API Specification

Status: Phase 2 baseline. Last updated: 2026-10-27. The FastAPI-generated OpenAPI document (`/api/v1/openapi.json`) is authoritative once implemented; this file records design intent.

## 1. Conventions

- Base path `/api/v1`. Breaking changes → `/api/v2`. Additive fields are non-breaking; clients must ignore unknown fields.
- JSON with `snake_case`. Timestamps are RFC 3339 UTC. IDs are UUIDv7 strings.
- **Errors** follow RFC 9457 `application/problem+json`:
  ```json
  {"type":"https://agent-p.dev/errors/validation","title":"Validation failed","status":422,
   "detail":"limits.max_minutes must be ≤ 15","instance":"/api/v1/tasks","request_id":"…","errors":[{"loc":["limits","max_minutes"],"msg":"…"}]}
  ```
- **Pagination**: cursor-based. `?limit=` (default 20, max 100) and `?cursor=` (opaque). Response: `{"items":[…],"next_cursor":"…"|null}`.
- **Idempotency**: `Idempotency-Key` header (UUID) is **required** on `POST /tasks/{id}/runs` and `POST /approvals/{id}/decision`, and optional elsewhere. The same key + same body returns the stored response; same key + different body → `422`.
- **Request IDs**: every response carries `X-Request-ID` (echoed if the client provides one).
- **Rate limits**: `429` with `Retry-After`.

## 2. Authentication and authorization

| Role | How | Can |
|---|---|---|
| anonymous | no cookie | `GET` on public tasks/runs/events/artifacts, `GET /meta` |
| operator | session cookie from `POST /auth/session` | everything |

Mutating requests also require an allowed `Origin` and an `X-CSRF-Token` header that matches the `agentp_csrf` cookie (double submit). CORS: explicit allowlist (`https://agent-p.vercel.app`, preview pattern `https://agent-p-*-<team>.vercel.app`, `http://localhost:5173`), `allow_credentials=true`.

## 3. Endpoints

### Auth and meta
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/session` | – | Body `{"token":"…"}` → sets session + CSRF cookies; 401 on mismatch (constant-time), rate-limited 5/min/IP |
| DELETE | `/auth/session` | op | Logout |
| GET | `/auth/me` | – | `{"role":"operator"|"anonymous"}` |
| GET | `/meta` | – | Templates, bundled repos, configured providers + models (no secrets), server limit maximums |
| GET | `/healthz` (root, not versioned) | – | Liveness |
| GET | `/readyz` | – | DB reachable, migrations at head, (worker heartbeat fresh) |

### Tasks
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/tasks` | op | Create a task |
| GET | `/tasks` | – | List (anonymous sees public only) |
| GET | `/tasks/{task_id}` | – | Detail + recent runs |

`POST /tasks` request:
```json
{
  "title": "Slow /orders endpoint",
  "goal": "Investigate why GET /orders is slow, identify the root cause, propose a fix, and verify it.",
  "template_key": "slow-endpoint-v1",
  "repo_source": {"kind": "bundled", "key": "demo-slow-api"},
  "model": "<configured model id>",
  "limits": {"max_minutes": 15, "max_llm_calls": 40, "max_total_tokens": 200000, "max_tool_calls": 80},
  "visibility": "public"
}
```
`repo_source` may instead be `{"kind":"github","url":"https://github.com/owner/repo"}`. Response `201` with the task.

### Runs
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/tasks/{task_id}/runs` | op | Queue a run → `202` with the run (status `queued`) |
| GET | `/runs` | – | List runs: `?status=&task_id=` |
| GET | `/runs/{run_id}` | – | Run snapshot: run, steps (graph), approvals, totals, `last_sequence` |
| POST | `/runs/{run_id}/cancel` | op | `202`; idempotent; `409` if already terminal |
| GET | `/runs/{run_id}/events` | – | Persisted events: `?after_seq=0&limit=500` → `{"items":[…],"next_after_seq":N|null}` |
| GET | `/runs/{run_id}/events/stream` | – | SSE live stream (below) |
| GET | `/runs/{run_id}/trace` | – | Nested view: steps → llm_calls → tool_invocations with timings (span tree) |
| GET | `/runs/{run_id}/tool-invocations/{id}` | – | Tool detail |
| GET | `/runs/{run_id}/artifacts` | – | Artifact list |
| GET | `/artifacts/{artifact_id}` | – | Metadata + inline content, or `/content` for a download |

### Approvals
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/approvals?status=pending` | op | Pending approvals |
| POST | `/approvals/{approval_id}/decision` | op | `{"decision":"approve"|"reject","comment":"…"}` → `200`; `409` if already decided |

### Metrics and settings
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/metrics/summary?window=7d` | – | Derived: run counts by status, success rate, avg/p95 duration, tokens, recent failures |
| GET | `/settings` | op | Non-secret settings + provider status (`configured: bool`) |
| PATCH | `/settings` | op | Default model/limits (validated against maximums) |

## 4. Live stream (SSE)

`GET /api/v1/runs/{run_id}/events/stream?after_seq=N` (or the `Last-Event-ID` header, which takes precedence).

```
id: 42
event: tool.completed
data: {"event_id":"…","run_id":"…","sequence_number":42,…}

: keepalive          (comment line every 15 s)
```

Server algorithm:
1. Subscribe to `LISTEN run_events` (one shared listener per API process, fanned out in-process).
2. Query and send all events with `seq > cursor` from the DB, advancing the cursor.
3. On each notification for this run, query `seq > cursor` again and send.
4. After a terminal workflow event is sent and no more rows exist, send `event: end` and close.

Guarantees: every event is persisted before it is sent; ordered by `sequence_number`; **at-least-once** delivery. Clients dedupe by `sequence_number` (ignore `seq ≤ last applied`) and, on a gap, refetch via `GET /events?after_seq=`.

## 5. Event schema (v1)

```json
{
  "event_id": "0192f…",
  "schema_version": 1,
  "run_id": "0192f…",
  "sequence_number": 42,
  "occurred_at": "2026-10-27T17:31:02.114Z",
  "event_type": "tool.completed",
  "step_id": "0192f…",
  "tool_invocation_id": "0192f…",
  "parent_event_id": "0192f…",
  "payload": { }
}
```

| event_type | payload (key fields) |
|---|---|
| `workflow.created` | `task_id`, `template_key`, `steps[]` (key, kind, role, title, depends_on), `limits`, `model` |
| `workflow.started` | `worker_id` |
| `workflow.waiting_approval` | `approval_id` |
| `workflow.completed` | `verification_label`, `report_artifact_id`, `totals` |
| `workflow.failed` | `reason`, `message`, `totals` |
| `workflow.cancel_requested` / `workflow.cancelled` | `actor` / `totals` |
| `step.started` | `attempt`, `input_summary` |
| `step.status_changed` | `from`, `to`, `reason` |
| `step.completed` | `output_summary`, `duration_ms` |
| `step.failed` | `error_type`, `message`, `retryable` |
| `step.skipped` | `reason` |
| `agent.message` | `kind` (`thought_summary`\|`narrative`), `text` — model-written narration, labeled as such in the UI |
| `llm.call_started` / `llm.call_completed` | `llm_call_id`, `model`; `input_tokens`, `output_tokens`, `latency_ms`, `finish_reason` |
| `llm.rate_limited` | `retry_after_ms` |
| `agent.output_invalid` | `validation_errors[]`, `attempt` |
| `tool.started` | `tool_name`, `input` (sanitized) |
| `tool.completed` | `output_summary`, `truncated`, `duration_ms` |
| `tool.failed` | `error_type`, `message`, `duration_ms` |
| `tool.denied` | `tool_name`, `reason` (not_allowed \| invalid_args \| policy:path \| budget) |
| `retry.scheduled` | `target` (llm_call\|tool\|step), `attempt`, `delay_ms`, `reason` |
| `approval.requested` | `approval_id`, `kind`, `artifact_id`, `summary` |
| `approval.resolved` | `approval_id`, `decision`, `comment`, `actor` |
| `sandbox.started` / `sandbox.finished` | `purpose` (clone\|install\|test\|bench), `image`, `limits`; `exit_code`, `duration_ms`, `oom_killed`, `timed_out` |
| `artifact.created` | `artifact_id`, `kind`, `name`, `size_bytes` |
| `budget.warning` | `budget`, `used`, `limit` (at 80%) |

Versioning: new event types and new optional payload fields keep `schema_version` 1; renamed or removed fields bump it. The frontend reducer ignores unknown event types and shows them generically in the timeline.
