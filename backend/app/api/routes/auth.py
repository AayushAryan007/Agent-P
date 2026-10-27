"""Operator sign-in/out (ADR-0004)."""

from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentSession, DbSession, Services, client_ip
from app.api.errors import ApiProblem
from app.api.schemas import LoginRequest, MeOut
from app.security import audit
from app.security.auth import SESSION_COOKIE, verify_admin_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, svc: Services, value: str) -> None:
    secure = svc.settings.cookie_secure
    # Frontend (Vercel) and API are different sites in prod, so the cookie must be SameSite=None; Secure.
    response.set_cookie(
        SESSION_COOKIE,
        value,
        max_age=svc.sessions.max_age,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/",
    )


@router.post("/session", response_model=MeOut)
async def login(
    body: LoginRequest, request: Request, response: Response, svc: Services, session: DbSession
) -> MeOut:
    ip = client_ip(request)
    if not svc.login_limiter.allow(ip):
        raise ApiProblem(
            429, "rate-limited", "Too many requests", "Too many sign-in attempts; try again in a minute"
        )
    if not verify_admin_token(svc.settings, body.token):
        audit.record(session, request, "anonymous", "auth.login_failed")
        await session.commit()
        raise ApiProblem(401, "unauthorized", "Unauthorized", "Invalid token")

    cookie, csrf = svc.sessions.issue()
    _set_session_cookie(response, svc, cookie)
    audit.record(session, request, "admin", "auth.login")
    await session.commit()
    return MeOut(role="operator", csrf_token=csrf)


@router.delete("/session", status_code=204)
async def logout(response: Response, svc: Services) -> Response:
    secure = svc.settings.cookie_secure
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="none" if secure else "lax"
    )
    response.status_code = 204
    return response


@router.get("/me", response_model=MeOut)
async def me(session: CurrentSession) -> MeOut:
    if session is None:
        return MeOut(role="anonymous", csrf_token=None)
    return MeOut(role="operator", csrf_token=session.get("csrf"))
