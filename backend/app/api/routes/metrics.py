"""Dashboard metrics, derived from stored runs on every request (FR-26). Nothing is cached or invented."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import Integer, func, select

from app.api.deps import CurrentRole, DbSession
from app.api.routes.runs import run_select, to_list_item
from app.api.schemas import MetricsSummary
from app.persistence.models import ApprovalRequest, Task, WorkflowRun, utcnow

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummary)
async def summary(
    session: DbSession,
    role: CurrentRole,
    window: Annotated[str, Query(pattern=r"^([1-9]|[1-8][0-9]|90)d$")] = "7d",
) -> MetricsSummary:
    since = utcnow() - timedelta(days=int(window[:-1]))
    visible = (
        select(WorkflowRun.id)
        .join(Task, Task.id == WorkflowRun.task_id)
        .where(WorkflowRun.queued_at >= since)
    )
    if role != "operator":
        visible = visible.where(Task.visibility == "public")
    in_window = WorkflowRun.id.in_(visible)

    by_status = dict(
        (
            await session.execute(
                select(WorkflowRun.status, func.count()).where(in_window).group_by(WorkflowRun.status)
            )
        ).all()
    )
    completed = by_status.get("completed", 0)
    verified = (
        await session.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(in_window, WorkflowRun.verification_label == "verified")
        )
    ) or 0
    terminal = completed + by_status.get("failed", 0) + by_status.get("cancelled", 0)

    duration_ms = func.extract("epoch", WorkflowRun.finished_at - WorkflowRun.started_at) * 1000
    finished = in_window & WorkflowRun.finished_at.is_not(None) & WorkflowRun.started_at.is_not(None)
    avg_ms, p95_ms = (
        await session.execute(
            select(func.avg(duration_ms), func.percentile_cont(0.95).within_group(duration_ms)).where(
                finished
            )
        )
    ).one()

    tokens = (
        await session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        WorkflowRun.totals["input_tokens"].astext.cast(Integer)
                        + WorkflowRun.totals["output_tokens"].astext.cast(Integer)
                    ),
                    0,
                )
            ).where(in_window)
        )
    ) or 0

    pending_q = (
        select(func.count())
        .select_from(ApprovalRequest)
        .join(WorkflowRun, WorkflowRun.id == ApprovalRequest.run_id)
        .where(ApprovalRequest.status == "pending", in_window)
    )
    pending = await session.scalar(pending_q) or 0

    failures = (
        await session.execute(
            run_select(role)
            .where(WorkflowRun.status == "failed", WorkflowRun.queued_at >= since)
            .order_by(WorkflowRun.finished_at.desc().nulls_last())
            .limit(5)
        )
    ).all()

    return MetricsSummary(
        window=window,
        runs_total=sum(by_status.values()),
        runs_by_status=by_status,
        success_rate=(completed / terminal) if terminal else None,
        avg_duration_ms=float(avg_ms) if avg_ms is not None else None,
        p95_duration_ms=float(p95_ms) if p95_ms is not None else None,
        total_tokens=int(tokens),
        pending_approvals=int(pending),
        verified_runs=int(verified),
        recent_failures=[to_list_item(r, t) for r, t in failures],
    )
