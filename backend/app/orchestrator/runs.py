"""Run creation and cancellation requests. Only these functions and the worker change run state."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.store import append_event
from app.orchestrator.templates import TEMPLATES
from app.persistence.models import RunStep, Task, WorkflowRun, utcnow

TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})


async def create_run(session: AsyncSession, task: Task, provider: str) -> WorkflowRun:
    """Insert a queued run, materialize its steps from the template, and record workflow.created.

    Runs in the caller's transaction so the run never exists without its first event.
    """
    template = TEMPLATES[task.template_key]
    run = WorkflowRun(
        task_id=task.id,
        status="queued",
        provider=provider,
        model=task.default_model,
        limits=task.limits,
    )
    session.add(run)
    await session.flush()

    steps = [
        RunStep(
            run_id=run.id,
            key=spec.key,
            kind=spec.kind,
            agent_role=spec.role,
            title=spec.title,
            depends_on=list(spec.depends_on),
            position=i,
        )
        for i, spec in enumerate(template.steps)
    ]
    session.add_all(steps)
    await session.flush()

    await append_event(
        session,
        run.id,
        "workflow.created",
        {
            "task_id": str(task.id),
            "template_key": template.key,
            "model": run.model,
            "limits": run.limits,
            "steps": [
                {
                    "id": str(s.id),
                    "key": s.key,
                    "kind": s.kind,
                    "role": s.agent_role,
                    "title": s.title,
                    "depends_on": s.depends_on,
                }
                for s in steps
            ],
        },
    )
    return run


class RunAlreadyFinished(Exception):
    pass


async def request_cancel(session: AsyncSession, run_id: uuid.UUID, actor: str) -> None:
    """Flag the run for cancellation; the worker observes the flag and performs the transition.

    A queued run has no worker yet, so it is cancelled directly.
    """
    run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id).with_for_update())
    if run is None:
        raise LookupError(run_id)
    if run.status in TERMINAL_RUN_STATUSES:
        raise RunAlreadyFinished(run.status)
    if run.cancel_requested:
        return  # idempotent

    run.cancel_requested = True
    await append_event(session, run_id, "workflow.cancel_requested", {"actor": actor})

    if run.status == "queued":
        run.status = "cancelled"
        run.status_reason = "cancelled_before_start"
        run.finished_at = utcnow()
        await session.execute(
            update(RunStep)
            .where(RunStep.run_id == run_id, RunStep.status == "pending")
            .values(status="cancelled")
        )
        await append_event(session, run_id, "workflow.cancelled", {"totals": run.totals, "actor": actor})
