"""Human approval decisions (FR-15). The API records the decision; the worker observes it and resumes."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.api import idempotency
from app.api.deps import DbSession, Operator
from app.api.errors import ApiProblem
from app.events.store import append_event
from app.persistence.models import ApprovalRequest, utcnow
from app.security import audit

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    kind: str
    status: str
    artifact_id: uuid.UUID | None
    summary: str | None
    comment: str | None
    decided_by: str | None


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(None, max_length=2000)


def to_out(a: ApprovalRequest) -> ApprovalOut:
    return ApprovalOut(
        id=a.id,
        run_id=a.run_id,
        step_id=a.step_id,
        kind=a.kind,
        status=a.status,
        artifact_id=a.artifact_id,
        summary=a.summary,
        comment=a.comment,
        decided_by=a.decided_by,
    )


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(session: DbSession, _: Operator, status: str = "pending") -> list[ApprovalOut]:
    rows = (
        await session.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == status)
            .order_by(ApprovalRequest.requested_at.desc())
            .limit(50)
        )
    ).all()
    return [to_out(a) for a in rows]


@router.post("/{approval_id}/decision")
async def decide(
    approval_id: uuid.UUID,
    body: DecisionRequest,
    request: Request,
    session: DbSession,
    actor: Operator,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    key = idempotency.validate_key(idempotency_key, required=True)
    assert key is not None
    scope = f"approval:{approval_id}"
    req_hash = idempotency.request_hash(body.model_dump())
    if (cached := await idempotency.lookup(session, scope, key, req_hash)) is not None:
        return JSONResponse(cached[1], status_code=cached[0])

    status = "approved" if body.decision == "approve" else "rejected"
    # Conditional update: exactly one decision can win, even under concurrent requests.
    approval = await session.scalar(
        update(ApprovalRequest)
        .where(ApprovalRequest.id == approval_id, ApprovalRequest.status == "pending")
        .values(status=status, decided_at=utcnow(), decided_by=actor, comment=body.comment)
        .returning(ApprovalRequest)
    )
    if approval is None:
        exists = await session.scalar(select(ApprovalRequest.status).where(ApprovalRequest.id == approval_id))
        if exists is None:
            raise ApiProblem(404, "not-found", "Not found", "Approval not found")
        raise ApiProblem(409, "already-decided", "Conflict", f"Approval is already {exists}")

    await append_event(
        session,
        approval.run_id,
        "approval.resolved",
        {"approval_id": str(approval.id), "decision": status, "comment": body.comment, "actor": actor},
        step_id=approval.step_id,
    )
    out = to_out(approval).model_dump(mode="json")
    await idempotency.store(session, scope, key, req_hash, 200, out)
    audit.record(session, request, actor, f"approval.{status}", "approval", approval.id)
    await session.commit()
    return JSONResponse(out)
