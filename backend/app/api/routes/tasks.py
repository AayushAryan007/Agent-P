"""Tasks and run creation."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api import idempotency
from app.api.deps import CurrentRole, DbSession, Operator, Services
from app.api.errors import ApiProblem
from app.api.routes.meta import max_limits, provider_for_model
from app.api.routes.runs import to_list_item
from app.api.schemas import CreateTaskRequest, Limits, Page, TaskOut
from app.orchestrator.runs import create_run
from app.orchestrator.templates import BUNDLED_REPOS, TEMPLATES
from app.persistence.models import Task
from app.security import audit
from app.security.auth import Role

router = APIRouter(prefix="/tasks", tags=["tasks"])


def to_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id,
        title=t.title,
        goal=t.goal,
        template_key=t.template_key,
        repo_source=t.repo_source,
        model=t.default_model,
        limits=Limits(**t.limits),
        visibility=t.visibility,
        created_at=t.created_at,
    )


async def get_visible_task(session: DbSession, task_id: uuid.UUID, role: Role) -> Task:
    q = select(Task).where(Task.id == task_id)
    if role != "operator":
        q = q.where(Task.visibility == "public")
    task = await session.scalar(q)
    if task is None:
        raise ApiProblem(404, "not-found", "Not found", "Task not found")
    return task


@router.post("", status_code=201, response_model=TaskOut)
async def create_task(
    body: CreateTaskRequest, request: Request, session: DbSession, svc: Services, actor: Operator
) -> TaskOut:
    if body.template_key not in TEMPLATES:
        raise ApiProblem(422, "validation", "Validation failed", f"Unknown template {body.template_key!r}")
    if body.repo_source.kind == "bundled" and body.repo_source.key not in BUNDLED_REPOS:
        raise ApiProblem(
            422, "validation", "Validation failed", f"Unknown bundled repository {body.repo_source.key!r}"
        )
    if provider_for_model(svc.settings, body.model) is None:
        raise ApiProblem(
            422,
            "model-unavailable",
            "Validation failed",
            f"Model {body.model!r} is not served by any configured provider",
        )
    maximum = max_limits(svc.settings)
    for name, value in body.limits:
        if value > getattr(maximum, name):
            raise ApiProblem(
                422, "validation", "Validation failed", f"limits.{name} must be ≤ {getattr(maximum, name)}"
            )

    task = Task(
        title=body.title,
        goal=body.goal,
        template_key=body.template_key,
        repo_source=body.repo_source.model_dump(),
        default_model=body.model,
        limits=body.limits.model_dump(),
        # GitHub-sourced runs are private by default (ADR-0004).
        visibility=body.visibility if body.repo_source.kind == "bundled" else "private",
        created_by=actor,
    )
    session.add(task)
    await session.flush()
    audit.record(session, request, actor, "task.create", "task", task.id)
    await session.commit()
    return to_out(task)


@router.get("", response_model=Page[TaskOut])
async def list_tasks(
    session: DbSession,
    role: CurrentRole,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: uuid.UUID | None = None,
) -> Page[TaskOut]:
    q = select(Task).order_by(Task.id.desc()).limit(limit + 1)
    if role != "operator":
        q = q.where(Task.visibility == "public")
    if cursor:
        q = q.where(Task.id < cursor)
    rows = (await session.scalars(q)).all()
    items = [to_out(t) for t in rows[:limit]]
    return Page[TaskOut](items=items, next_cursor=str(items[-1].id) if len(rows) > limit else None)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: uuid.UUID, session: DbSession, role: CurrentRole) -> TaskOut:
    return to_out(await get_visible_task(session, task_id, role))


@router.post("/{task_id}/runs", status_code=202)
async def start_run(
    task_id: uuid.UUID,
    request: Request,
    session: DbSession,
    svc: Services,
    actor: Operator,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    key = idempotency.validate_key(idempotency_key, required=True)
    assert key is not None
    scope = f"start_run:{task_id}"
    req_hash = idempotency.request_hash({"task_id": str(task_id)})
    if (cached := await idempotency.lookup(session, scope, key, req_hash)) is not None:
        return JSONResponse(cached[1], status_code=cached[0])

    task = await get_visible_task(session, task_id, "operator")
    provider = provider_for_model(svc.settings, task.default_model)
    if provider is None:
        raise ApiProblem(
            422,
            "model-unavailable",
            "Validation failed",
            f"Model {task.default_model!r} is no longer served by a configured provider",
        )

    run = await create_run(session, task, provider)
    body = to_list_item(run, task.title).model_dump(mode="json")
    if not await idempotency.store(session, scope, key, req_hash, 202, body):
        # A concurrent request with the same key committed first; discard ours and return theirs.
        await session.rollback()
        cached = await idempotency.lookup(session, scope, key, req_hash)
        assert cached is not None
        return JSONResponse(cached[1], status_code=cached[0])
    audit.record(session, request, actor, "run.create", "run", run.id)
    await session.commit()
    return JSONResponse(body, status_code=202)
