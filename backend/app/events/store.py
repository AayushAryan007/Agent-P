"""Appending and reading execution events.

`append_event` must run inside the caller's transaction, together with the
state change it describes. Sequence numbers are assigned under a row lock on
the run, and NOTIFY is issued in the same transaction, so PostgreSQL delivers
the notification only if (and after) the event is committed.
"""

import json
import uuid
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.schema import MAX_PAYLOAD_BYTES, NOTIFY_CHANNEL, SCHEMA_VERSION, EventOut
from app.persistence.models import ExecutionEvent, WorkflowRun
from app.security.redaction import redact


class PayloadTooLarge(ValueError):
    pass


async def append_event(
    session: AsyncSession,
    run_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    step_id: uuid.UUID | None = None,
    tool_invocation_id: uuid.UUID | None = None,
    parent_event_id: uuid.UUID | None = None,
) -> ExecutionEvent:
    clean = redact(payload or {})
    if len(json.dumps(clean, default=str)) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLarge(
            f"{event_type} payload exceeds {MAX_PAYLOAD_BYTES} bytes; store it as an artifact"
        )

    # Row lock serializes concurrent appends for the same run (e.g. two parallel steps).
    seq = (
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == run_id)
            .values(last_sequence=WorkflowRun.last_sequence + 1)
            .returning(WorkflowRun.last_sequence)
        )
    ).scalar_one()

    event = ExecutionEvent(
        run_id=run_id,
        sequence_number=seq,
        schema_version=SCHEMA_VERSION,
        event_type=event_type,
        step_id=step_id,
        tool_invocation_id=tool_invocation_id,
        parent_event_id=parent_event_id,
        payload=clean,
    )
    session.add(event)
    await session.flush()
    await session.execute(
        text("SELECT pg_notify(:channel, :msg)"), {"channel": NOTIFY_CHANNEL, "msg": f"{run_id}:{seq}"}
    )
    return event


async def list_events(
    session: AsyncSession, run_id: uuid.UUID, after_seq: int = 0, limit: int = 500
) -> list[EventOut]:
    rows = (
        await session.scalars(
            select(ExecutionEvent)
            .where(ExecutionEvent.run_id == run_id, ExecutionEvent.sequence_number > after_seq)
            .order_by(ExecutionEvent.sequence_number)
            .limit(limit)
        )
    ).all()
    return [to_out(e) for e in rows]


def to_out(e: ExecutionEvent) -> EventOut:
    return EventOut(
        event_id=e.id,
        schema_version=e.schema_version,
        run_id=e.run_id,
        sequence_number=e.sequence_number,
        occurred_at=e.occurred_at,
        event_type=e.event_type,
        step_id=e.step_id,
        tool_invocation_id=e.tool_invocation_id,
        parent_event_id=e.parent_event_id,
        payload=e.payload,
    )
