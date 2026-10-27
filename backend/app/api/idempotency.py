"""Idempotency-Key support for unsafe POSTs (docs/API_SPECIFICATION.md §1)."""

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiProblem
from app.persistence.models import IdempotencyKey


def request_hash(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


async def lookup(
    session: AsyncSession, scope: str, key: str, req_hash: str
) -> tuple[int, dict[str, Any]] | None:
    row = await session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.scope == scope, IdempotencyKey.key == key)
    )
    if row is None:
        return None
    if row.request_hash != req_hash:
        raise ApiProblem(
            422,
            "idempotency-mismatch",
            "Validation failed",
            "Idempotency-Key was already used with a different request body",
        )
    return row.response_status, row.response_body


async def store(
    session: AsyncSession, scope: str, key: str, req_hash: str, status: int, body: dict[str, Any]
) -> bool:
    """Record the response in the caller's transaction. Returns False if a concurrent request won the race."""
    result = await session.execute(
        insert(IdempotencyKey)
        .values(scope=scope, key=key, request_hash=req_hash, response_status=status, response_body=body)
        .on_conflict_do_nothing()
        .returning(IdempotencyKey.key)
    )
    return result.scalar_one_or_none() is not None


def validate_key(key: str | None, required: bool) -> str | None:
    if key is None:
        if required:
            raise ApiProblem(
                400, "idempotency-key-required", "Bad request", "Idempotency-Key header is required"
            )
        return None
    if not (8 <= len(key) <= 128) or not key.replace("-", "").isalnum():
        raise ApiProblem(
            400, "idempotency-key-invalid", "Bad request", "Idempotency-Key must be 8-128 [A-Za-z0-9-]"
        )
    return key
