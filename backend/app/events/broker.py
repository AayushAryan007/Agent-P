"""Fan-out of PostgreSQL NOTIFY messages to SSE subscribers in this API process (ADR-0006).

One dedicated asyncpg connection LISTENs on `run_events`. Notifications only
wake subscribers; the subscribers then read events from the database. That
keeps the database the single source of truth: a lost notification costs
latency, never correctness, because subscribers also re-query periodically
and after a listener reconnect.
"""

import asyncio
import contextlib
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator

import asyncpg
import structlog

from app.events.schema import NOTIFY_CHANNEL

log = structlog.get_logger(__name__)


class EventBroker:
    def __init__(self, dsn: str) -> None:
        # asyncpg wants a plain postgres:// DSN, not SQLAlchemy's driver-qualified URL.
        self._dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        self._subscribers: dict[uuid.UUID, set[asyncio.Event]] = defaultdict(set)
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="event-broker")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    @contextlib.asynccontextmanager
    async def subscribe(self, run_id: uuid.UUID) -> AsyncIterator[asyncio.Event]:
        wake = asyncio.Event()
        self._subscribers[run_id].add(wake)
        try:
            yield wake
        finally:
            subs = self._subscribers.get(run_id)
            if subs is not None:
                subs.discard(wake)
                if not subs:
                    del self._subscribers[run_id]

    def _on_notify(self, _conn: object, _pid: int, _channel: str, payload: str) -> None:
        run_part = payload.split(":", 1)[0]
        try:
            run_id = uuid.UUID(run_part)
        except ValueError:
            return
        for wake in self._subscribers.get(run_id, ()):
            wake.set()

    def _wake_all(self) -> None:
        for subs in self._subscribers.values():
            for wake in subs:
                wake.set()

    async def _run(self) -> None:
        backoff = 0.5
        while not self._stopping.is_set():
            conn: asyncpg.Connection | None = None
            try:
                conn = await asyncpg.connect(self._dsn)
                closed = asyncio.Event()
                conn.add_termination_listener(lambda _c, ev=closed: ev.set())
                await conn.add_listener(NOTIFY_CHANNEL, self._on_notify)
                log.info("event_broker.listening", channel=NOTIFY_CHANNEL)
                backoff = 0.5
                # Anything committed while we were disconnected is picked up by a re-query.
                self._wake_all()
                await closed.wait()
                raise ConnectionError("LISTEN connection closed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("event_broker.disconnected", error=str(exc), retry_in_s=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10)
            finally:
                if conn is not None and not conn.is_closed():
                    await conn.close()
