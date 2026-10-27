# ADR-0001: Custom state machine for orchestration (not LangGraph)

- Status: Accepted
- Date: 2026-10-27

## Context

AGENT-P's core product is the execution event log: live graph, replay, metrics and verification all derive from it. The orchestrator must emit a persisted event for every state transition, pause for human approval, enforce budgets, and be testable without an LLM.

## Options

1. **LangGraph.** Provides graph execution, checkpointing, and `interrupt()` for human-in-the-loop. But its state and checkpoints live in its own store; we would translate its callbacks into our event schema, keeping two sources of truth. Its abstractions also hide the concepts (state machines, DAG scheduling) this project is meant to make visible.
2. **Custom asyncio state machine.** A small engine: a DAG of steps, an explicit transition table per entity (run, agent run, tool invocation), and a scheduler that starts steps whose dependencies are complete. Every transition is a DB write plus event append in one transaction.

## Decision

Option 2. The orchestrator is the single owner of workflow state; events are written in the same transaction as state changes.

## Consequences

- + One source of truth; replay is trivial; state transitions are unit-testable with a fake LLM.
- + Approval is just a `waiting_approval` state resolved by an API call.
- − We implement retries, budgets, cancellation, and timeouts ourselves (~a few hundred lines).
- − Crash-resume is not free; MVP marks interrupted runs `failed` (resume is P2, made feasible by the event log).
- Revisit if workflows become dynamic/agent-authored graphs where LangGraph's flexibility pays off.
