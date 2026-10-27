"""Liveness and readiness probes (unversioned, used by Caddy/uptime checks)."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def expected_migration_head() -> str | None:
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: DbSession) -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
        current = (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()
        checks["migrations"] = "ok" if current == expected_migration_head() else f"behind ({current})"
    except Exception as exc:
        checks.setdefault("database", f"error: {type(exc).__name__}")
    ready = all(v == "ok" for v in checks.values()) and "migrations" in checks
    return JSONResponse(
        {"status": "ready" if ready else "not_ready", "checks": checks}, status_code=200 if ready else 503
    )
