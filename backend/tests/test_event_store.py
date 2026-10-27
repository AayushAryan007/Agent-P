"""Event log guarantees: ordered sequence numbers under concurrency, append-only, NOTIFY only on commit."""

import asyncio

import asyncpg
import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError

from app.events.schema import NOTIFY_CHANNEL
from app.events.store import PayloadTooLarge, append_event, list_events
from app.orchestrator.runs import create_run
from app.persistence.db import Database
from app.persistence.models import ExecutionEvent, WorkflowRun
from tests.conftest import TEST_DB_URL, make_task


async def new_run(db: Database) -> WorkflowRun:
    async with db.sessionmaker() as s:
        run = await create_run(s, await make_task(s), "gemini")
        await s.commit()
        return run


async def test_create_run_records_workflow_created_with_steps(db: Database) -> None:
    run = await new_run(db)
    async with db.sessionmaker() as s:
        events = await list_events(s, run.id)
    assert [e.sequence_number for e in events] == [1]
    assert events[0].event_type == "workflow.created"
    assert [st["key"] for st in events[0].payload["steps"]][:3] == ["prepare_workspace", "plan", "baseline"]


async def test_concurrent_appends_get_unique_gapless_sequence(db: Database) -> None:
    run = await new_run(db)

    async def append(i: int) -> None:
        async with db.sessionmaker() as s:
            await append_event(s, run.id, "test.concurrent", {"i": i})
            await asyncio.sleep(0.01)  # hold the row lock briefly to force contention
            await s.commit()

    await asyncio.gather(*(append(i) for i in range(25)))

    async with db.sessionmaker() as s:
        seqs = [e.sequence_number for e in await list_events(s, run.id, limit=100)]
        last = await s.scalar(select(WorkflowRun.last_sequence).where(WorkflowRun.id == run.id))
    assert seqs == list(range(1, 27))
    assert last == 26


async def test_rolled_back_append_does_not_consume_sequence(db: Database) -> None:
    run = await new_run(db)
    async with db.sessionmaker() as s:
        await append_event(s, run.id, "test.discarded")
        await s.rollback()
    async with db.sessionmaker() as s:
        e = await append_event(s, run.id, "test.kept")
        await s.commit()
    assert e.sequence_number == 2


async def test_events_are_append_only(db: Database) -> None:
    run = await new_run(db)
    async with db.sessionmaker() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            await s.execute(update(ExecutionEvent).values(event_type="tampered"))
        await s.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            await s.execute(delete(ExecutionEvent))
        await s.rollback()
        # Deleting the whole run (retention) cascades and is allowed.
        await s.execute(delete(WorkflowRun).where(WorkflowRun.id == run.id))
        await s.commit()
        assert await s.scalar(text("SELECT count(*) FROM execution_events")) == 0


async def test_notify_is_delivered_only_after_commit(db: Database) -> None:
    run = await new_run(db)
    received: asyncio.Queue[str] = asyncio.Queue()
    conn = await asyncpg.connect(TEST_DB_URL.replace("+asyncpg", ""))
    await conn.add_listener(NOTIFY_CHANNEL, lambda *args: received.put_nowait(args[3]))
    try:
        async with db.sessionmaker() as s:
            await append_event(s, run.id, "test.pending")
            await asyncio.sleep(0.2)
            assert received.empty(), "notification leaked before commit"
            await s.commit()
        assert await asyncio.wait_for(received.get(), 2) == f"{run.id}:2"

        async with db.sessionmaker() as s:
            await append_event(s, run.id, "test.rolled_back")
            await s.rollback()
        await asyncio.sleep(0.2)
        assert received.empty(), "rolled-back event must not notify"
    finally:
        await conn.close()


async def test_oversized_payload_is_rejected(db: Database) -> None:
    run = await new_run(db)
    async with db.sessionmaker() as s:
        with pytest.raises(PayloadTooLarge):
            await append_event(s, run.id, "test.big", {"blob": "x" * 40_000})


async def test_payload_secrets_are_redacted(db: Database) -> None:
    run = await new_run(db)
    async with db.sessionmaker() as s:
        await append_event(
            s,
            run.id,
            "tool.completed",
            {
                "api_key": "AIzaSyD-not-a-real-key-000000000000000",
                "output": "GEMINI_API_KEY=abc123",
                "input_tokens": 7,
            },
        )
        await s.commit()
        e = (await list_events(s, run.id))[-1]
    assert e.payload == {"api_key": "[REDACTED]", "output": "[REDACTED]", "input_tokens": 7}
