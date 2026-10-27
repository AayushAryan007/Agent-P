"""Audit trail for operator actions (SECURITY_MODEL.md §4.7)."""

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import AuditLog


def record(
    session: AsyncSession,
    request: Request,
    actor: str,
    action: str,
    target_type: str | None = None,
    target_id: object | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add an audit row to the caller's transaction."""
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
            details=details,
        )
    )
