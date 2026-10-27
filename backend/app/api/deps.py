"""Shared FastAPI dependencies: settings, DB session, auth role, operator guard."""

import re
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiProblem
from app.config import Settings
from app.events.broker import EventBroker
from app.persistence.db import Database
from app.security.auth import CSRF_HEADER, SESSION_COOKIE, LoginRateLimiter, Role, SessionCodec


@dataclass
class AppServices:
    """Process-wide services created in the app lifespan. Stored on app.state, never as module globals."""

    settings: Settings
    db: Database
    broker: EventBroker
    sessions: SessionCodec
    login_limiter: LoginRateLimiter


def services(request: Request) -> AppServices:
    svc: AppServices = request.app.state.services
    return svc


Services = Annotated[AppServices, Depends(services)]


async def db_session(svc: Services) -> AsyncIterator[AsyncSession]:
    async with svc.db.sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(db_session)]


def current_session(request: Request, svc: Services) -> dict[str, str] | None:
    data = svc.sessions.read(request.cookies.get(SESSION_COOKIE))
    return data if data and data.get("role") == "operator" else None


CurrentSession = Annotated[dict[str, str] | None, Depends(current_session)]


def current_role(session: CurrentSession) -> Role:
    return "operator" if session else "anonymous"


CurrentRole = Annotated[Role, Depends(current_role)]


def _origin_allowed(svc: AppServices, origin: str) -> bool:
    if origin in svc.settings.cors_origins:
        return True
    return bool(svc.settings.cors_origin_regex and re.fullmatch(svc.settings.cors_origin_regex, origin))


def require_operator(request: Request, svc: Services, session: CurrentSession) -> str:
    """Operator session + CSRF protection for unsafe methods.

    Synchronizer token: the CSRF token lives inside the signed session cookie and is handed to the
    SPA in the /auth responses; the SPA echoes it in X-CSRF-Token. A cross-site attacker can make the
    browser send the cookie but cannot read the token (CORS), so it cannot forge the header. A
    double-submit *cookie* would not work here: the SPA (Vercel) cannot read cookies of the API domain.
    """
    if session is None:
        raise ApiProblem(401, "unauthorized", "Unauthorized", "Operator sign-in required")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and not _origin_allowed(svc, origin):
            raise ApiProblem(403, "forbidden", "Forbidden", "Origin not allowed")
        header = request.headers.get(CSRF_HEADER, "")
        expected = session.get("csrf", "")
        if not (header and expected and secrets.compare_digest(header, expected)):
            raise ApiProblem(403, "csrf", "Forbidden", "Missing or invalid CSRF token")
    return "admin"


Operator = Annotated[str, Depends(require_operator)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
