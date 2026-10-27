# ADR-0005: Server-Sent Events for live run updates

- Status: Accepted
- Date: 2026-10-27

## Context

The browser needs ordered, live execution events and must recover from disconnects without losing or duplicating events. All client→server actions (approve, cancel) are ordinary REST calls.

## Options

- **WebSocket:** bidirectional; requires our own reconnect, resume, and heartbeat protocol; cookie auth on cross-site WebSockets is awkward.
- **SSE:** one-way over plain HTTP; the browser `EventSource` reconnects automatically and sends `Last-Event-ID`; works with credentials and through Caddy/CDNs.
- **Polling:** simplest, but higher latency and load.

## Decision

SSE, with `id` = per-run `sequence_number`. The DB remains the source of truth; the stream is a delivery mechanism (at-least-once, clients dedupe by sequence). A paged `GET /events?after_seq=` endpoint serves replay and gap repair.

## Consequences

- + Reconnect and resume come almost free; simple server code.
- − HTTP/1.1 browsers allow ~6 connections per origin; we open one stream per viewed run, which is fine. Caddy serves HTTP/2.
- Revisit if we need client→server streaming (e.g. interactive agent chat).
