"""SSE stream: catch-up from the DB, live delivery via NOTIFY, Last-Event-ID resume, and end-of-stream."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.events.store import append_event
from app.orchestrator.runs import create_run
from app.persistence.db import Database
from tests.conftest import make_task


async def new_run(db: Database) -> uuid.UUID:
    async with db.sessionmaker() as s:
        run = await create_run(s, await make_task(s), "gemini")
        await s.commit()
        return run.id


async def append(
    db: Database, run_id: uuid.UUID, event_type: str, payload: dict[str, Any] | None = None
) -> None:
    async with db.sessionmaker() as s:
        await append_event(s, run_id, event_type, payload)
        await s.commit()


async def read_frames(lines: AsyncIterator[str], n: int) -> list[dict[str, Any]]:
    """Parse SSE frames (id/event/data), skipping comments/pings, until n data frames are read.

    Takes one shared line iterator per response so it can be called repeatedly on a live stream.
    """
    frames: list[dict[str, Any]] = []
    frame: dict[str, Any] = {}
    async for line in lines:
        if line == "":
            if "data" in frame:
                frames.append(frame)
                if len(frames) == n:
                    return frames
            frame = {}
        elif line.startswith(":"):
            continue
        else:
            field, _, value = line.partition(":")
            frame[field] = value.lstrip(" ")
    return frames


async def test_stream_catches_up_then_delivers_live(anon: httpx.AsyncClient, db: Database) -> None:
    run_id = await new_run(db)
    await append(db, run_id, "workflow.started")

    async with anon.stream("GET", f"/api/v1/runs/{run_id}/events/stream") as resp:
        lines = resp.aiter_lines()
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        history = await read_frames(lines, 2)
        assert [f["id"] for f in history] == ["1", "2"]

        # A commit in another session must arrive via NOTIFY well before the 5 s safety poll.
        loop = asyncio.get_running_loop()
        start = loop.time()
        await append(db, run_id, "step.started", {"attempt": 1})
        (live,) = await asyncio.wait_for(read_frames(lines, 1), timeout=3)
        assert live["id"] == "3"
        assert json.loads(live["data"])["event_type"] == "step.started"
        assert loop.time() - start < 1.5


async def test_last_event_id_resumes_without_duplicates(anon: httpx.AsyncClient, db: Database) -> None:
    run_id = await new_run(db)
    for t in ("workflow.started", "step.started", "step.completed"):
        await append(db, run_id, t)

    async with anon.stream(
        "GET", f"/api/v1/runs/{run_id}/events/stream", params={"after_seq": 0}, headers={"Last-Event-ID": "2"}
    ) as resp:
        lines = resp.aiter_lines()
        frames = await read_frames(lines, 2)
    assert [f["id"] for f in frames] == ["3", "4"]


async def test_stream_ends_after_terminal_event(anon: httpx.AsyncClient, db: Database) -> None:
    run_id = await new_run(db)
    await append(db, run_id, "workflow.failed", {"reason": "test"})

    async with anon.stream("GET", f"/api/v1/runs/{run_id}/events/stream") as resp:
        lines = resp.aiter_lines()
        frames = await asyncio.wait_for(read_frames(lines, 3), timeout=3)
    assert [f.get("event", "message") for f in frames] == ["message", "message", "end"]


async def test_private_runs_are_not_streamed_to_anonymous(anon: httpx.AsyncClient, db: Database) -> None:
    async with db.sessionmaker() as s:
        run = await create_run(s, await make_task(s, visibility="private"), "gemini")
        await s.commit()
    r = await anon.get(f"/api/v1/runs/{run.id}/events/stream")
    assert r.status_code == 404
