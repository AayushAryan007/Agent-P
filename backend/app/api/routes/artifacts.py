"""Artifacts and tool invocation details (read-only, visibility-checked)."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentRole, DbSession
from app.api.errors import ApiProblem
from app.api.routes.runs import get_visible_run
from app.persistence.models import ApprovalRequest, Artifact, ToolInvocation

router = APIRouter(tags=["artifacts"])


class ArtifactMeta(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None
    kind: str
    name: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class ArtifactOut(ArtifactMeta):
    text: str | None
    data: dict[str, Any] | None


class ToolInvocationOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    llm_call_id: uuid.UUID | None
    tool_name: str
    status: str
    input: dict[str, Any]
    output_summary: dict[str, Any] | None
    output_truncated: bool
    error: dict[str, Any] | None
    trace_id: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None


class PendingApprovalOut(BaseModel):
    id: uuid.UUID
    step_id: uuid.UUID
    status: str
    artifact_id: uuid.UUID | None
    summary: str | None


def _meta(a: Artifact) -> dict[str, Any]:
    return {
        "id": a.id,
        "run_id": a.run_id,
        "step_id": a.step_id,
        "kind": a.kind,
        "name": a.name,
        "content_type": a.content_type,
        "size_bytes": a.size_bytes,
        "sha256": a.sha256,
        "created_at": a.created_at,
    }


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactMeta])
async def list_artifacts(run_id: uuid.UUID, session: DbSession, role: CurrentRole) -> list[ArtifactMeta]:
    await get_visible_run(session, run_id, role)
    rows = (
        await session.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at))
    ).all()
    return [ArtifactMeta(**_meta(a)) for a in rows]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(artifact_id: uuid.UUID, session: DbSession, role: CurrentRole) -> ArtifactOut:
    a = await session.scalar(select(Artifact).where(Artifact.id == artifact_id))
    if a is None:
        raise ApiProblem(404, "not-found", "Not found", "Artifact not found")
    await get_visible_run(session, a.run_id, role)
    return ArtifactOut(**_meta(a), text=a.inline_text, data=a.inline_json)


@router.get("/runs/{run_id}/tool-invocations/{invocation_id}", response_model=ToolInvocationOut)
async def get_tool_invocation(
    run_id: uuid.UUID, invocation_id: uuid.UUID, session: DbSession, role: CurrentRole
) -> ToolInvocationOut:
    await get_visible_run(session, run_id, role)
    t = await session.scalar(
        select(ToolInvocation).where(ToolInvocation.id == invocation_id, ToolInvocation.run_id == run_id)
    )
    if t is None:
        raise ApiProblem(404, "not-found", "Not found", "Tool invocation not found")
    return ToolInvocationOut(
        id=t.id,
        run_id=t.run_id,
        step_id=t.step_id,
        llm_call_id=t.llm_call_id,
        tool_name=t.tool_name,
        status=t.status,
        input=t.input,
        output_summary=t.output_summary,
        output_truncated=t.output_truncated,
        error=t.error,
        trace_id=t.trace_id,
        started_at=t.started_at,
        finished_at=t.finished_at,
        duration_ms=t.duration_ms,
    )


@router.get("/runs/{run_id}/approvals", response_model=list[PendingApprovalOut])
async def run_approvals(run_id: uuid.UUID, session: DbSession, role: CurrentRole) -> list[PendingApprovalOut]:
    await get_visible_run(session, run_id, role)
    rows = (await session.scalars(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id))).all()
    return [
        PendingApprovalOut(
            id=a.id, step_id=a.step_id, status=a.status, artifact_id=a.artifact_id, summary=a.summary
        )
        for a in rows
    ]
