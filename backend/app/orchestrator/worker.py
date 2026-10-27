"""Worker: claims queued runs (SKIP LOCKED), executes them, renews leases, honours cancellation (ADR-0006)."""

import asyncio
import contextlib
import os
import socket
import uuid
from datetime import timedelta

import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.events.store import append_event
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.orchestrator.budget import Budget
from app.orchestrator.context import RunContext, StepInfo, TaskInfo
from app.orchestrator.engine import RunFailed, execute
from app.orchestrator.workspace import Workspace
from app.persistence.db import Database
from app.persistence.models import ApprovalRequest, RunStep, Task, WorkflowRun, utcnow
from app.sandbox.runner import SandboxRunner

log = structlog.get_logger(__name__)

ProviderFactory = dict[str, LLMProvider]


def build_providers(settings: Settings) -> ProviderFactory:
    providers: ProviderFactory = {}
    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider(settings.gemini_api_key.get_secret_value())
    return providers


class Worker:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        providers: ProviderFactory,
        sandbox: SandboxRunner | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.providers = providers
        self.sandbox = sandbox or SandboxRunner(settings.sandbox_image)
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.active: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        await self.recover_stale()
        removed = await asyncio.to_thread(self.sandbox.cleanup_orphans)
        log.info("worker.started", worker_id=self.worker_id, orphan_sandboxes_removed=removed)
        while not self._stop.is_set():
            if len(self.active) < self.settings.worker_max_runs and (run_id := await self.claim()):
                self.active[run_id] = asyncio.create_task(self._supervise(run_id), name=f"run:{run_id}")
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.worker_poll_s)
        for t in self.active.values():
            t.cancel()
        await asyncio.gather(*self.active.values(), return_exceptions=True)

    async def run_once(self, run_id: uuid.UUID) -> None:
        """Execute one already-claimed run to completion (used by tests and run_forever)."""
        await self._supervise(run_id)

    # ---- claiming and leases -------------------------------------------------------------

    async def claim(self) -> uuid.UUID | None:
        async with self.db.sessionmaker() as s:
            row = (
                await s.execute(
                    text(
                        "UPDATE workflow_runs SET status='running', worker_id=:w, "
                        "lease_expires_at=now() + make_interval(secs => :lease_s), "
                        "started_at=now() WHERE id = (SELECT id FROM workflow_runs WHERE status='queued' "
                        "AND cancel_requested = false ORDER BY queued_at FOR UPDATE SKIP LOCKED LIMIT 1) "
                        "RETURNING id"
                    ),
                    {"w": self.worker_id, "lease_s": self.settings.worker_lease_s},
                )
            ).first()
            if row is None:
                await s.rollback()
                return None
            run_id: uuid.UUID = row[0]
            await append_event(s, run_id, "workflow.started", {"worker_id": self.worker_id})
            await s.commit()
        log.info("run.claimed", run_id=str(run_id))
        return run_id

    async def recover_stale(self) -> None:
        """Runs whose worker died (lease expired) cannot be resumed in the MVP; fail them visibly."""
        async with self.db.sessionmaker() as s:
            stale = (
                await s.scalars(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.status.in_(("running", "waiting_approval")),
                        # Database clock only: worker and DB clocks may differ (e.g. Colima VM).
                        WorkflowRun.lease_expires_at < func.now(),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for run in stale:
                run.status, run.status_reason, run.finished_at = "failed", "interrupted", utcnow()
                await s.execute(
                    update(RunStep)
                    .where(
                        RunStep.run_id == run.id,
                        RunStep.status.in_(("pending", "running", "waiting_approval")),
                    )
                    .values(status="cancelled", finished_at=utcnow())
                )
                await s.execute(
                    update(ApprovalRequest)
                    .where(ApprovalRequest.run_id == run.id, ApprovalRequest.status == "pending")
                    .values(status="cancelled")
                )
                await append_event(
                    s,
                    run.id,
                    "workflow.failed",
                    {
                        "reason": "interrupted",
                        "message": "The worker executing this run stopped unexpectedly.",
                        "totals": run.totals,
                    },
                )
                log.warning("run.recovered_as_failed", run_id=str(run.id))
            await s.commit()

    async def _heartbeat(self, run_id: uuid.UUID, engine_task: asyncio.Task[object]) -> None:
        interval = max(1.0, self.settings.worker_lease_s / 3)
        while not engine_task.done():
            async with self.db.sessionmaker() as s:
                cancel = await s.scalar(
                    update(WorkflowRun)
                    .where(WorkflowRun.id == run_id)
                    .values(lease_expires_at=func.now() + timedelta(seconds=self.settings.worker_lease_s))
                    .returning(WorkflowRun.cancel_requested)
                )
                await s.commit()
            if cancel:
                engine_task.cancel()
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(asyncio.shield(engine_task), timeout=min(interval, 1.0))

    # ---- execution -----------------------------------------------------------------------

    async def _load_context(self, run_id: uuid.UUID) -> RunContext:
        async with self.db.sessionmaker() as s:
            run = await s.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id))
            assert run is not None
            task = await s.scalar(select(Task).where(Task.id == run.task_id))
            assert task is not None
            steps = (
                await s.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.position))
            ).all()
        provider = self.providers.get(run.provider)
        if provider is None:
            raise RunFailed(
                "provider_unavailable", f"LLM provider {run.provider!r} is not configured on this worker"
            )
        fallback = self.settings.gemini_fallback_model if run.provider == "gemini" else None
        return RunContext(
            run_id=run_id,
            task=TaskInfo(task.id, task.title, task.goal, task.repo_source),
            settings=self.settings,
            db=self.db,
            provider=provider,
            sandbox=self.sandbox,
            budget=Budget.from_limits(run.limits, run.totals),
            workspace=Workspace(self.settings.workspace_root / str(run_id)),
            model=run.model,
            fallback_model=fallback,
            steps={
                st.key: StepInfo(
                    st.id, st.key, st.kind, st.agent_role, st.title, list(st.depends_on), st.status
                )
                for st in steps
            },
        )

    async def _supervise(self, run_id: uuid.UUID) -> None:
        structlog.contextvars.bind_contextvars(run_id=str(run_id))
        ctx: RunContext | None = None
        try:
            ctx = await self._load_context(run_id)
            engine_task = asyncio.create_task(execute(ctx))
            heartbeat = asyncio.create_task(self._heartbeat(run_id, engine_task))
            try:
                result = await engine_task
            finally:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat
            await ctx.set_run_status(
                "completed",
                "workflow.completed",
                {
                    "verification_label": result["verification_label"],
                    "report_artifact_id": result["report_artifact_id"],
                    "totals": ctx.budget.totals(),
                },
                verification_label=result["verification_label"],
            )
        except asyncio.CancelledError:
            # Operator cancel → record it. Worker shutdown → leave the run; its lease expires and
            # recover_stale() marks it interrupted, which is the honest outcome.
            async with self.db.sessionmaker() as s:
                requested = await s.scalar(
                    select(WorkflowRun.cancel_requested).where(WorkflowRun.id == run_id)
                )
            if not requested:
                raise
            await self._finish_cancelled(run_id, ctx)
        except RunFailed as exc:
            await self._finish_failed(run_id, ctx, exc.reason, str(exc))
        except Exception as exc:
            log.exception("run.crashed")
            await self._finish_failed(run_id, ctx, "internal_error", f"{type(exc).__name__}: {exc}")
        finally:
            if ctx is not None:
                await asyncio.to_thread(ctx.workspace.cleanup)
            self.active.pop(run_id, None)
            structlog.contextvars.unbind_contextvars("run_id")

    async def _close_open_steps(self, s: AsyncSession, run_id: uuid.UUID) -> None:
        open_steps = (
            await s.scalars(
                select(RunStep).where(
                    RunStep.run_id == run_id, RunStep.status.in_(("pending", "running", "waiting_approval"))
                )
            )
        ).all()
        for st in open_steps:
            prev = st.status
            st.status, st.finished_at = "cancelled", utcnow()
            await append_event(
                s,
                run_id,
                "step.status_changed",
                {"from": prev, "to": "cancelled", "reason": "run ended"},
                step_id=st.id,
            )
        await s.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.run_id == run_id, ApprovalRequest.status == "pending")
            .values(status="cancelled")
        )

    async def _finish_failed(
        self, run_id: uuid.UUID, ctx: RunContext | None, reason: str, message: str
    ) -> None:
        async with self.db.sessionmaker() as s:
            run = await s.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id).with_for_update())
            assert run is not None
            if run.status in ("completed", "failed", "cancelled"):
                return
            await self._close_open_steps(s, run_id)
            totals = ctx.budget.totals() if ctx else run.totals
            run.status, run.status_reason, run.finished_at, run.totals = (
                "failed",
                reason[:200],
                utcnow(),
                totals,
            )
            await append_event(
                s, run_id, "workflow.failed", {"reason": reason, "message": message[:1000], "totals": totals}
            )
            await s.commit()
        log.warning("run.failed", reason=reason, message=message[:300])

    async def _finish_cancelled(self, run_id: uuid.UUID, ctx: RunContext | None) -> None:
        async with self.db.sessionmaker() as s:
            run = await s.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id).with_for_update())
            assert run is not None
            if run.status in ("completed", "failed", "cancelled"):
                return
            await self._close_open_steps(s, run_id)
            totals = ctx.budget.totals() if ctx else run.totals
            run.status, run.status_reason, run.finished_at, run.totals = (
                "cancelled",
                "cancelled_by_operator",
                utcnow(),
                totals,
            )
            await append_event(s, run_id, "workflow.cancelled", {"totals": totals})
            await s.commit()
        log.info("run.cancelled")
