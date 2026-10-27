"""Single-admin session auth with CSRF protection (ADR-0004)."""

import secrets
import time
from collections import defaultdict, deque
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import Settings

Role = Literal["operator", "anonymous"]

SESSION_COOKIE = "agentp_session"
CSRF_HEADER = "X-CSRF-Token"

_hasher = PasswordHasher()


def hash_token(token: str) -> str:
    return _hasher.hash(token)


def verify_admin_token(settings: Settings, token: str) -> bool:
    if settings.admin_token_hash is None:
        # Still burn time so a missing configuration is not distinguishable by timing.
        _hasher.hash(token)
        return False
    try:
        return _hasher.verify(settings.admin_token_hash.get_secret_value(), token)
    except (VerificationError, InvalidHashError):
        return False


class SessionCodec:
    def __init__(self, settings: Settings) -> None:
        self._s = URLSafeTimedSerializer(settings.session_secret.get_secret_value(), salt="agentp-session")
        self.max_age = settings.session_max_age_s

    def issue(self) -> tuple[str, str]:
        """Return (session cookie value, csrf token)."""
        csrf = secrets.token_urlsafe(32)
        return self._s.dumps({"role": "operator", "csrf": csrf}), csrf

    def read(self, value: str | None) -> dict[str, str] | None:
        if not value:
            return None
        try:
            data = self._s.loads(value, max_age=self.max_age)
        except BadSignature:
            return None
        return data if isinstance(data, dict) else None


class LoginRateLimiter:
    """In-process sliding window. Adequate for a single API instance; move to Redis when scaling out."""

    def __init__(self, limit: int = 5, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True
