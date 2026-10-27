"""Runs: listing, snapshot, cancellation, persisted events, and the live SSE stream."""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette import EventSourceResponse

from app.api.deps import CurrentRole, DbSession, Operator, Services
from app.api.errors import ApiProblem
from app.api.schemas import EventsPage, Limits, Page, RunDetail, RunListItem, RunStatus, RunStepOut, RunTotals
from app.events.schema import TERMINAL_EVENT_TYPES
from app.events.store import list_events
from app.orchestrator.runs import RunAlreadyFinished, request_cancel
from app.persistence.models import RunStep, Task, WorkflowRun
from app.security import audit
from app.security.auth import Role

router = APIRouter(prefix="/runs", tags=["runs"])

STREAM_BATCH = 200
# Safety net: re-query even without a notification, so a lost NOTIFY only costs latency.
STREAM_POLL_S = 5.0


def run_select(role: Role) -> Select[WorkflowRun, str]:
    q = select(WorkflowRun, Task.title).join(Task, Task.id == WorkflowRun.task_id)
    if role != "operator":
        q = q.where(Task.visibility == "public")
    return q


def to_list_item(run: WorkflowRun, title: str) -> RunListItem:
    return RunListItem(
        id=run.id,
        task_id=run.task_id,
        task_title=title,
        status=run.status,
        status_reason=run.status_reason,
        verification_label=run.verification_label,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        totals=RunTotals(**run.totals),
    )


async def get_visible_run(session: AsyncSession, run_id: uuid.UUID, role: Role) -> tuple[WorkflowRun, str]:
    row = (await session.execute(run_select(role).where(WorkflowRun.id == run_id))).first()
    if row is None:
        raise ApiProblem(404, "not-found", "Not found", "Run not found")
    run, title = row
    return run, title


@router.get("", response_model=Page[RunListItem])
async def list_runs(
    session: DbSession,
    role: CurrentRole,
    status: RunStatus | None = None,
    task_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: uuid.UUID | None = None,
) -> Page[RunListItem]:
    # UUIDv7 ids are time-ordered, so the last id is a stable keyset cursor.
    q = run_select(role).order_by(WorkflowRun.id.desc()).limit(limit + 1)
    if status:
        q = q.where(WorkflowRun.status == status)
    if task_id:
        q = q.where(WorkflowRun.task_id == task_id)
    if cursor:
        q = q.where(WorkflowRun.id < cursor)
    rows = (await session.execute(q)).all()
    items = [to_list_item(r, t) for r, t in rows[:limit]]
    return Page[RunListItem](items=items, next_cursor=str(items[-1].id) if len(rows) > limit else None)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: uuid.UUID, session: DbSession, role: CurrentRole) -> RunDetail:
    run, title = await get_visible_run(session, run_id, role)
    steps = (
        await session.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.position))
    ).all()
    return RunDetail(
        **to_list_item(run, title).model_dump(),
        model=run.model,
        limits=Limits(**run.limits),
        last_sequence=run.last_sequence,
        steps=[
            RunStepOut(
                id=s.id,
                key=s.key,
                kind=s.kind,
                role=s.agent_role,
                title=s.title,
                depends_on=s.depends_on,
                status=s.status,
                attempt=s.attempt,
                started_at=s.started_at,
                finished_at=s.finished_at,
            )
            for s in steps
        ],
    )


@router.post("/{run_id}/cancel", status_code=202, response_model=RunListItem)
async def cancel_run(run_id: uuid.UUID, request: Request, session: DbSession, actor: Operator) -> RunListItem:
    try:
        await request_cancel(session, run_id, actor)
    except LookupError:
        raise ApiProblem(404, "not-found", "Not found", "Run not found") from None
    except RunAlreadyFinished as exc:
        raise ApiProblem(409, "run-finished", "Conflict", f"Run already {exc}") from None
    audit.record(session, request, actor, "run.cancel", "run", run_id)
    await session.commit()
    run, title = await get_visible_run(session, run_id, "operator")
    return to_list_item(run, title)


@router.get("/{run_id}/events", response_model=EventsPage)
async def get_events(
    run_id: uuid.UUID,
    session: DbSession,
    role: CurrentRole,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> EventsPage:
    await get_visible_run(session, run_id, role)
    events = await list_events(session, run_id, after_seq, limit + 1)
    page = events[:limit]
    return EventsPage(items=page, next_after_seq=page[-1].sequence_number if len(events) > limit else None)


@router.get("/{run_id}/events/stream")
async def stream_events(
    run_id: uuid.UUID,
    request: Request,
    svc: Services,
    role: CurrentRole,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header()] = None,
) -> EventSourceResponse:
    async with svc.db.sessionmaker() as session:
        await get_visible_run(session, run_id, role)

    # Last-Event-ID (sent by EventSource on reconnect) takes precedence over the query parameter.
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after_seq

    async def generate() -> AsyncIterator[dict[str, Any]]:
        nonlocal cursor
        async with svc.broker.subscribe(run_id) as wake:
            ended = False
            while not await request.is_disconnected():
                wake.clear()  # clear before querying so a commit during the query still wakes us
                async with svc.db.sessionmaker() as session:
                    events = await list_events(session, run_id, cursor, STREAM_BATCH)
                for e in events:
                    yield {"id": str(e.sequence_number), "data": e.model_dump_json()}
                    cursor = e.sequence_number
                    ended = ended or e.event_type in TERMINAL_EVENT_TYPES
                if len(events) == STREAM_BATCH:
                    continue
                if ended:
                    yield {"event": "end", "data": "{}"}
                    return
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(wake.wait(), timeout=STREAM_POLL_S)

    return EventSourceResponse(
        generate(), ping=15, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )
