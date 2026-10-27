"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import AppServices
from app.api.errors import install_error_handlers
from app.api.routes import approvals, artifacts, auth, health, meta, metrics, runs, tasks
from app.config import Settings, get_settings
from app.events.broker import EventBroker
from app.observability.logging import RequestContextMiddleware, configure_logging
from app.persistence.db import Database
from app.security.auth import CSRF_HEADER, LoginRateLimiter, SessionCodec

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=settings.env == "prod")
    if settings.env == "prod" and "insecure" in settings.session_secret.get_secret_value():
        raise RuntimeError("SESSION_SECRET must be set in production")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings)
        broker = EventBroker(str(settings.database_url))
        await broker.start()
        app.state.services = AppServices(
            settings=settings,
            db=db,
            broker=broker,
            sessions=SessionCodec(settings),
            login_limiter=LoginRateLimiter(limit=settings.login_attempts_per_minute),
        )
        try:
            yield
        finally:
            await broker.stop()
            await db.dispose()

    app = FastAPI(
        title="AGENT-P API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", CSRF_HEADER, "Last-Event-ID", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    for module in (auth, meta, tasks, runs, approvals, artifacts, metrics):
        app.include_router(module.router, prefix=API_PREFIX)
    return app
