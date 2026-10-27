"""Redaction of secrets from anything that is persisted, logged, or streamed (SECURITY_MODEL.md §4.6)."""

import re
from typing import Any

REDACTED = "[REDACTED]"

# Anchored at the end so counters like "input_tokens" are not mistaken for secrets.
_SENSITIVE_KEY = re.compile(
    r"(^|[_\-])(api[_\-]?key|secret|token|password|passwd|authorization|cookie|credentials?)$", re.I
)

_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google API key
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),  # Groq key
    re.compile(r"sk-[0-9A-Za-z_\-]{20,}"),  # OpenAI-style keys
    re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),  # GitHub tokens
    re.compile(r"(?i)bearer\s+[0-9a-z._\-]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?im)^\s*([A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*\S+"),
]


def redact_text(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(REDACTED, value)
    return value


def redact(value: Any) -> Any:
    """Recursively redact dicts/lists/strings. Values under sensitive-looking keys are dropped entirely."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            k: (REDACTED if isinstance(k, str) and _SENSITIVE_KEY.search(k) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value
