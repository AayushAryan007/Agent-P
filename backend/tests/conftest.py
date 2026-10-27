"""Test fixtures. Tests run against a real PostgreSQL (`agentp_test` in the Compose stack),
because SKIP LOCKED, LISTEN/NOTIFY, and triggers cannot be faked meaningfully.

    docker compose up -d postgres && uv run pytest
"""

import asyncio
import os
import socket
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.main import create_app
from app.persistence.db import Database
from app.persistence.models import Task
from app.security.auth import hash_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://agentp:agentp@localhost:5433/agentp_test"
)
ADMIN_TOKEN = "test-admin-token"
ORIGIN = "http://localhost:5173"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        env="test",
        database_url=TEST_DB_URL,  # type: ignore[arg-type]
        admin_token_hash=SecretStr(hash_token(ADMIN_TOKEN)),
        session_secret=SecretStr("test-session-secret"),
        gemini_api_key=SecretStr("test-key-not-used"),
        cors_origins=[ORIGIN],
        login_attempts_per_minute=1000,  # every test signs in; the limiter itself is unit-tested
    )


@pytest.fixture(scope="session", autouse=True)
def migrated(settings: Settings) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def db(settings: Settings) -> AsyncIterator[Database]:
    database = Database(settings)
    yield database
    await database.dispose()


@pytest.fixture(autouse=True)
async def clean(db: Database) -> None:
    async with db.engine.begin() as conn:
        # TRUNCATE does not fire row-level triggers, so it bypasses the append-only guard by design.
        await conn.execute(
            text(
                "TRUNCATE tasks, workflow_runs, run_steps, execution_events, tool_invocations, llm_calls, "
                "approval_requests, artifacts, audit_log, idempotency_keys, app_settings CASCADE"
            )
        )


@pytest.fixture
async def session(db: Database) -> AsyncIterator[AsyncSession]:
    async with db.sessionmaker() as s:
        yield s


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
async def server(settings: Settings) -> AsyncIterator[str]:
    """A real uvicorn server, so SSE streaming is exercised over actual HTTP."""
    port = _free_port()
    config = uvicorn.Config(
        create_app(settings), host="127.0.0.1", port=port, log_level="warning", lifespan="on"
    )
    srv = uvicorn.Server(config)
    task = asyncio.create_task(srv.serve())
    while not srv.started:
        await asyncio.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    await task


@pytest.fixture
async def anon(server: str) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=server, headers={"Origin": ORIGIN}, timeout=10) as c:
        yield c


@pytest.fixture
async def operator(server: str) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=server, headers={"Origin": ORIGIN}, timeout=10) as c:
        r = await c.post("/api/v1/auth/session", json={"token": ADMIN_TOKEN})
        assert r.status_code == 200, r.text
        c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        yield c


def task_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "title": "Slow GET /orders",
        "goal": "Investigate why GET /orders is slow and verify a fix.",
        "template_key": "slow-endpoint-v1",
        "repo_source": {"kind": "bundled", "key": "demo-slow-api"},
        "model": "gemini-3.8-flash",
        "limits": {"max_minutes": 10, "max_llm_calls": 20, "max_total_tokens": 100000, "max_tool_calls": 40},
        "visibility": "public",
    }
    body.update(overrides)
    return body


async def make_task(session: AsyncSession, visibility: str = "public") -> Task:
    task = Task(
        title="t",
        goal="g" * 20,
        template_key="slow-endpoint-v1",
        repo_source={"kind": "bundled", "key": "demo-slow-api"},
        default_model="gemini-3.8-flash",
        limits={"max_minutes": 10, "max_llm_calls": 20, "max_total_tokens": 100000, "max_tool_calls": 40},
        visibility=visibility,
        created_by="admin",
    )
    session.add(task)
    await session.flush()
    return task
