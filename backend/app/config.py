"""Centralized configuration. Every setting comes from the environment (or backend/.env in dev)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("admin_token_hash", "gemini_api_key", "groq_api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        # `GEMINI_API_KEY=` in .env must mean "not configured", not "configured with an empty key".
        return None if isinstance(v, str) and not v.strip() else v

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://agentp:agentp@localhost:5432/agentp"),
        description="SQLAlchemy async URL (asyncpg driver).",
    )

    # Explicit allowlist; no wildcard (SECURITY_MODEL.md §4.5). Comma-separated in env.
    cors_origins: list[str] = ["http://localhost:5173"]
    # Regex for Vercel preview deployments, e.g. https://agent-p-[a-z0-9-]+-team\.vercel\.app
    cors_origin_regex: str | None = None

    # Auth (ADR-0004). The plaintext admin token is never stored; only its argon2 hash.
    admin_token_hash: SecretStr | None = None
    session_secret: SecretStr = SecretStr("dev-insecure-session-secret-change-me")
    session_max_age_s: int = 12 * 3600
    cookie_secure: bool = False
    login_attempts_per_minute: int = 5

    # LLM providers (ADR-0002). Keys stay server-side.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"

    # Run limits: defaults offered in the UI and hard server-side maximums.
    default_max_minutes: int = 15
    default_max_llm_calls: int = 40
    default_max_total_tokens: int = 200_000
    default_max_tool_calls: int = 80
    max_max_minutes: int = 15
    max_max_llm_calls: int = 80
    max_max_total_tokens: int = 500_000
    max_max_tool_calls: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
