"""RunContext: everything a step needs, and the only path by which execution state changes.

Each method opens a short transaction that updates the state row(s) *and* appends the event that
describes the change, so the event log and the current-state tables can never disagree.
No LLM or sandbox call ever happens inside one of these transactions.
"""

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.events.store import append_event
from app.llm.base import LLMProvider
from app.orchestrator.budget import Budget
from app.orchestrator.transitions import check_run, check_step
from app.orchestrator.workspace import Workspace
from app.persistence.db import Database
from app.persistence.models import Artifact, ExecutionEvent, RunStep, WorkflowRun, utcnow
from app.sandbox.runner import SandboxRunner
from app.tools.base import ArtifactDraft

INLINE_ARTIFACT_LIMIT = 256 * 1024


@dataclass
class StepInfo:
    id: uuid.UUID
    key: str
    kind: str
    role: str | None
    title: str
    depends_on: list[str]
    status: str


@dataclass
class TaskInfo:
    id: uuid.UUID
    title: str
    goal: str
    repo_source: dict[str, Any]


@dataclass
class RunContext:
    run_id: uuid.UUID
    task: TaskInfo
    settings: Settings
    db: Database
    provider: LLMProvider
    sandbox: SandboxRunner
    budget: Budget
    workspace: Workspace
    model: str
    fallback_model: str | None
    steps: dict[str, StepInfo]
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Steps that finished as skipped; downstream steps use this to decide whether they apply.
    skipped: set[str] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ---- low-level -------------------------------------------------------------------------

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        step_id: uuid.UUID | None = None,
        tool_invocation_id: uuid.UUID | None = None,
        parent_event_id: uuid.UUID | None = None,
    ) -> ExecutionEvent:
        async with self.db.sessionmaker() as s:
            e = await append_event(
                s,
                self.run_id,
                event_type,
                payload,
                step_id=step_id,
                tool_invocation_id=tool_invocation_id,
                parent_event_id=parent_event_id,
            )
            await s.commit()
            return e

    async def save_totals(self, s: AsyncSession) -> None:
        await s.execute(
            update(WorkflowRun).where(WorkflowRun.id == self.run_id).values(totals=self.budget.totals())
        )

    # ---- run / step status -----------------------------------------------------------------

    async def set_run_status(
        self, target: str, event_type: str, payload: dict[str, Any] | None = None, **fields: Any
    ) -> None:
        async with self.db.sessionmaker() as s:
            run = await s.scalar(select(WorkflowRun).where(WorkflowRun.id == self.run_id).with_for_update())
            assert run is not None
            check_run(run.status, target)
            run.status = target
            for k, v in fields.items():
                setattr(run, k, v)
            if target in ("completed", "failed", "cancelled"):
                run.finished_at = utcnow()
            run.totals = self.budget.totals()
            await append_event(s, self.run_id, event_type, payload)
            await s.commit()

    async def set_step_status(
        self,
        key: str,
        target: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        **fields: Any,
    ) -> None:
        info = self.steps[key]
        # The lock keeps parallel steps from interleaving transitions in this process.
        async with self._lock, self.db.sessionmaker() as s:
            step = await s.scalar(select(RunStep).where(RunStep.id == info.id).with_for_update())
            assert step is not None
            check_step(step.status, target)
            step.status = target
            now = utcnow()
            if target == "running" and step.started_at is None:
                step.started_at = now
            if target in ("completed", "failed", "cancelled", "skipped"):
                step.finished_at = now
            for k, v in fields.items():
                setattr(step, k, v)
            await append_event(s, self.run_id, event_type, payload, step_id=info.id)
            await s.commit()
            info.status = target

    # ---- artifacts -------------------------------------------------------------------------

    async def store_artifact(self, step_key: str | None, draft: ArtifactDraft) -> uuid.UUID:
        body = (draft.text or "") + (
            json.dumps(draft.json, sort_keys=True, default=str) if draft.json else ""
        )
        raw = body.encode()
        text = draft.text if draft.text is not None and len(draft.text) <= INLINE_ARTIFACT_LIMIT else None
        if draft.text is not None and text is None:
            text = draft.text[:INLINE_ARTIFACT_LIMIT] + "\n… [truncated]"
        step_id = self.steps[step_key].id if step_key else None
        async with self.db.sessionmaker() as s:
            art = Artifact(
                run_id=self.run_id,
                step_id=step_id,
                kind=draft.kind,
                name=draft.name,
                content_type=draft.content_type,
                size_bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
                inline_text=text,
                inline_json=draft.json,
            )
            s.add(art)
            await s.flush()
            await append_event(
                s,
                self.run_id,
                "artifact.created",
                {"artifact_id": str(art.id), "kind": draft.kind, "name": draft.name, "size_bytes": len(raw)},
                step_id=step_id,
            )
            await s.commit()
            return art.id

    async def cancel_requested(self) -> bool:
        async with self.db.sessionmaker() as s:
            return bool(
                await s.scalar(select(WorkflowRun.cancel_requested).where(WorkflowRun.id == self.run_id))
            )
