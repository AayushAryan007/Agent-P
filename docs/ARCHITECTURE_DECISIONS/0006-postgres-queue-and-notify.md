# ADR-0006: Separate worker process; PostgreSQL as run queue and event bus

- Status: Accepted
- Date: 2026-10-27

## Context

Runs last minutes and must not die when the API process restarts for a deploy. The API must stream events produced elsewhere. The master prompt asks us not to add Redis/Celery/brokers without justification.

## Options

1. Run workflows as asyncio tasks inside the API process — simplest, but every API restart kills runs, and long work shares the event loop with request handling.
2. Celery + Redis — proven, but adds two moving parts and a second state store.
3. **Worker process + Postgres**: the worker claims runs with `SELECT … FOR UPDATE SKIP LOCKED`, holds a lease, and publishes `NOTIFY run_events` inside the same transaction that inserts each event. The API holds one `LISTEN` connection and fans out in-process to SSE clients.

## Decision

Option 3. Same codebase and image, two entrypoints: `agentp api` and `agentp worker`.

## Consequences

- + No new infrastructure; NOTIFY is transactional (sent only on commit), which matches "persist before stream".
- + Safe scaling: more workers can be added later; SKIP LOCKED prevents double-claiming.
- − NOTIFY payloads are capped at 8 KB → we send only `run_id:seq` and read the event from the DB.
- − A stalled worker is detected via an expired lease; MVP marks those runs `failed(interrupted)`.
