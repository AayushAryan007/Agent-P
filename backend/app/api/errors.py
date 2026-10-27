"""RFC 9457 problem+json error responses (docs/API_SPECIFICATION.md §1)."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_BASE = "https://agent-p.dev/errors/"
log = structlog.get_logger(__name__)


class ApiProblem(Exception):
    def __init__(self, status: int, slug: str, title: str, detail: str | None = None) -> None:
        self.status = status
        self.slug = slug
        self.title = title
        self.detail = detail


def problem(
    request: Request, status: int, slug: str, title: str, detail: str | None = None, **extra: Any
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": ERROR_BASE + slug,
        "title": title,
        "status": status,
        "instance": request.url.path,
        "request_id": request.scope.get("state", {}).get("request_id"),
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


_TITLES = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    422: "Validation failed",
    429: "Too many requests",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def _api_problem(request: Request, exc: ApiProblem) -> JSONResponse:
        return problem(request, exc.status, exc.slug, exc.title, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = _TITLES.get(exc.status_code, "Error")
        resp = problem(request, exc.status_code, title.lower().replace(" ", "-"), title, str(exc.detail))
        if exc.headers:
            resp.headers.update(exc.headers)
        return resp

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        first = errors[0] if errors else None
        detail = f"{'.'.join(str(p) for p in first['loc'][1:])}: {first['msg']}" if first else None
        return problem(request, 422, "validation", "Validation failed", detail, errors=errors)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return problem(request, 500, "internal", "Internal server error")
