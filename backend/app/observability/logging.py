"""Structured logging (JSON in prod) with request/run correlation via contextvars."""

import logging
import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.security.redaction import redact


def _redact_processor(
    _logger: object, _name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    return redact(event_dict)  # type: ignore[no-any-return]


def configure_logging(level: str, json_logs: bool) -> None:
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware:
    """Assigns X-Request-ID, binds it to log context, and logs one access line per request.

    Pure ASGI (not BaseHTTPMiddleware) so streaming SSE responses are not buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.log = structlog.get_logger("http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode()[:64]
        request_id = incoming if incoming.replace("-", "").isalnum() else str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope["path"]
            if path not in ("/healthz",):
                self.log.info(
                    "request",
                    method=scope["method"],
                    path=path,
                    status=status,
                    duration_ms=round((time.perf_counter() - start) * 1000, 1),
                )
