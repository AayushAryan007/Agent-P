"""Pure unit tests (no database)."""

import pytest

from app.orchestrator.templates import TEMPLATES, StepSpec, Template
from app.security.auth import LoginRateLimiter
from app.security.redaction import REDACTED, redact


def test_redaction_keeps_counters_and_drops_secrets() -> None:
    data = {
        "input_tokens": 10,
        "max_total_tokens": 5,
        "access_token": "x",
        "Authorization": "Bearer abcdefghijklmnopqrstu",
        "nested": [{"password": "p"}, "key ghp_" + "a" * 36],
        "env": "PATH=/usr/bin\nOPENAI_API_KEY=sk-live",
    }
    out = redact(data)
    assert out["input_tokens"] == 10 and out["max_total_tokens"] == 5
    assert out["access_token"] == REDACTED and out["Authorization"] == REDACTED
    assert out["nested"] == [{"password": REDACTED}, f"key {REDACTED}"]
    assert out["env"] == f"PATH=/usr/bin\n{REDACTED}"


def test_login_rate_limiter_blocks_after_limit() -> None:
    limiter = LoginRateLimiter(limit=3, window_s=60)
    assert [limiter.allow("1.2.3.4") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("5.6.7.8")


def test_template_steps_are_topologically_ordered() -> None:
    for t in TEMPLATES.values():
        seen: set[str] = set()
        for s in t.steps:
            assert set(s.depends_on) <= seen
            seen.add(s.key)


def test_template_rejects_forward_dependencies() -> None:
    with pytest.raises(ValueError, match="depends on unknown"):
        Template("bad", "Bad", "", (StepSpec("a", "system", "A", None, ("b",)), StepSpec("b", "system", "B")))


def test_blank_secrets_mean_not_configured() -> None:
    from app.config import Settings

    s = Settings(_env_file=None, gemini_api_key="", groq_api_key="  ", admin_token_hash="")  # type: ignore[call-arg, arg-type]
    assert s.gemini_api_key is None and s.groq_api_key is None and s.admin_token_hash is None


def test_redacts_ai_studio_auth_keys() -> None:
    assert redact("using AQ.FakeKeyForTests_0000000000000000000000 now") == f"using {REDACTED} now"
