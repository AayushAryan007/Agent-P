"""End-to-end orchestration: worker + agents + tool gate + approval + verification + report.

The LLM is scripted (deterministic). `test_full_run_in_real_sandbox` also runs the demo repository's real
tests and benchmark inside the hardened sandbox container; it is skipped when no Docker engine/image is available.
"""

import asyncio
import uuid
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.events.store import list_events
from app.llm.scripted import ScriptedProvider
from app.orchestrator.runs import create_run
from app.orchestrator.worker import Worker
from app.persistence.db import Database
from app.persistence.models import ApprovalRequest, RunStep, ToolInvocation, WorkflowRun
from app.sandbox.runner import SandboxRunner, SandboxUnavailable
from tests.conftest import make_task
from tests.workflow_support import FakeSandbox, scripts


def worker_for(
    settings: Settings, db: Database, provider: ScriptedProvider, sandbox: Any, tmp: Path
) -> Worker:
    s = settings.model_copy(update={"workspace_root": tmp, "worker_lease_s": 30})
    return Worker(s, db, {"gemini": provider}, sandbox=sandbox)  # type: ignore[dict-item]


async def start(db: Database, worker: Worker) -> tuple[uuid.UUID, asyncio.Task[None]]:
    async with db.sessionmaker() as s:
        await create_run(s, await make_task(s), "gemini")
        await s.commit()
    run_id = await worker.claim()
    assert run_id is not None
    return run_id, asyncio.create_task(worker.run_once(run_id))


async def wait_for_approval(
    db: Database, run_id: uuid.UUID, task: asyncio.Task[None], timeout: float = 60
) -> uuid.UUID:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if task.done():
            task.result()
            raise AssertionError("run finished before requesting approval")
        async with db.sessionmaker() as s:
            a = await s.scalar(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id))
        if a is not None:
            return a.id
        await asyncio.sleep(0.1)
    raise AssertionError("approval was not requested in time")


async def decide(operator: httpx.AsyncClient, approval_id: uuid.UUID, decision: str) -> None:
    r = await operator.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": decision, "comment": "looks right" if decision == "approve" else "no"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 200, r.text


async def state(db: Database, run_id: uuid.UUID) -> tuple[WorkflowRun, dict[str, str], list[str]]:
    async with db.sessionmaker() as s:
        run = await s.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id))
        steps = {
            st.key: st.status
            for st in (await s.scalars(select(RunStep).where(RunStep.run_id == run_id))).all()
        }
        events = [e.event_type for e in await list_events(s, run_id, limit=1000)]
    assert run is not None
    return run, steps, events


async def test_approved_run_is_verified_with_full_event_trail(
    settings: Settings, db: Database, operator: httpx.AsyncClient, tmp_path: Path
) -> None:
    provider = ScriptedProvider(scripts())
    worker = worker_for(settings, db, provider, FakeSandbox(), tmp_path)
    run_id, task = await start(db, worker)

    approval_id = await wait_for_approval(db, run_id, task)
    run, steps, _ = await state(db, run_id)
    assert run.status == "waiting_approval" and steps["approve_patch"] == "waiting_approval"
    assert steps["verify"] == "pending"  # nothing is applied before approval

    await decide(operator, approval_id, "approve")
    await asyncio.wait_for(task, 30)

    run, steps, events = await state(db, run_id)
    assert run.status == "completed" and run.verification_label == "verified"
    assert all(v == "completed" for v in steps.values()), steps
    counts = Counter(events)
    assert counts["tool.denied"] == 2  # path traversal + tool outside the allowlist
    assert counts["agent.output_invalid"] == 1 and counts["retry.scheduled"] >= 1
    assert counts["approval.requested"] == counts["approval.resolved"] == 1
    assert events[-1] == "workflow.completed"
    assert run.totals["llm_calls"] == len(provider.calls)

    async with db.sessionmaker() as s:
        denied = (await s.scalars(select(ToolInvocation).where(ToolInvocation.status == "denied"))).all()
    assert sorted(d.error["reason"] for d in denied if d.error) == ["not_allowed", "policy"]
    # The workspace is cleaned up after the run.
    assert not (tmp_path / str(run_id)).exists()


async def test_rejected_patch_skips_verification_and_is_not_verified(
    settings: Settings, db: Database, operator: httpx.AsyncClient, tmp_path: Path
) -> None:
    sandbox = FakeSandbox()
    worker = worker_for(
        settings,
        db,
        ScriptedProvider({**scripts(invalid_first=False), "[role:review]": []}),
        sandbox,
        tmp_path,
    )
    run_id, task = await start(db, worker)
    await decide(operator, await wait_for_approval(db, run_id, task), "reject")
    await asyncio.wait_for(task, 30)

    run, steps, _ = await state(db, run_id)
    assert run.status == "completed" and run.verification_label == "not_verified"
    assert steps["verify"] == steps["review"] == "skipped"
    assert not any(
        c.mounts and c.mounts[0].host.name == "patched" for c in sandbox.calls
    )  # never ran patched code


async def test_cancel_while_waiting_for_approval(
    settings: Settings, db: Database, operator: httpx.AsyncClient, tmp_path: Path
) -> None:
    worker = worker_for(settings, db, ScriptedProvider(scripts(invalid_first=False)), FakeSandbox(), tmp_path)
    run_id, task = await start(db, worker)
    await wait_for_approval(db, run_id, task)
    r = await operator.post(f"/api/v1/runs/{run_id}/cancel")
    assert r.status_code == 202
    await asyncio.wait_for(task, 10)

    run, steps, events = await state(db, run_id)
    assert run.status == "cancelled"
    assert steps["approve_patch"] == "cancelled" and steps["report"] == "cancelled"
    assert events[-1] == "workflow.cancelled"
    async with db.sessionmaker() as s:
        a = await s.scalar(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id))
    assert a is not None and a.status == "cancelled"


async def test_llm_call_budget_fails_the_run(settings: Settings, db: Database, tmp_path: Path) -> None:
    worker = worker_for(settings, db, ScriptedProvider(scripts()), FakeSandbox(), tmp_path)
    async with db.sessionmaker() as s:
        task_row = await make_task(s)
        task_row.limits = {**task_row.limits, "max_llm_calls": 2}
        await create_run(s, task_row, "gemini")
        await s.commit()
    run_id = await worker.claim()
    assert run_id is not None
    await asyncio.wait_for(worker.run_once(run_id), 30)

    run, steps, events = await state(db, run_id)
    assert run.status == "failed" and run.status_reason == "budget_exceeded:llm_calls"
    assert "workflow.failed" in events and steps["report"] == "cancelled"


async def test_stale_runs_are_recovered_as_interrupted(
    settings: Settings, db: Database, tmp_path: Path
) -> None:
    worker = worker_for(settings, db, ScriptedProvider({}), FakeSandbox(), tmp_path)
    async with db.sessionmaker() as s:
        await create_run(s, await make_task(s), "gemini")
        await s.commit()
    run_id = await worker.claim()
    assert run_id is not None
    async with db.sessionmaker() as s:
        run = await s.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id))
        assert run is not None
        run.lease_expires_at = func.now() - timedelta(minutes=5)  # type: ignore[assignment]
        await s.commit()
    await worker.recover_stale()
    run, _, events = await state(db, run_id)
    assert run.status == "failed" and run.status_reason == "interrupted" and events[-1] == "workflow.failed"


def _real_sandbox(settings: Settings) -> SandboxRunner:
    runner = SandboxRunner(settings.sandbox_image, run_label="agentp-test")
    try:
        runner.ensure_image()
    except SandboxUnavailable as exc:
        pytest.skip(str(exc))
    return runner


@pytest.mark.sandbox
async def test_full_run_in_real_sandbox(
    settings: Settings, db: Database, operator: httpx.AsyncClient
) -> None:
    sandbox = _real_sandbox(settings)
    # Workspaces must be bind-mountable by the engine (under $HOME for Colima), so not pytest's /tmp.
    root = settings.workspace_root / "test-runs"
    worker = worker_for(settings, db, ScriptedProvider(scripts(invalid_first=False)), sandbox, root)
    run_id, task = await start(db, worker)
    await decide(operator, await wait_for_approval(db, run_id, task, timeout=180), "approve")
    await asyncio.wait_for(task, 300)

    run, steps, events = await state(db, run_id)
    async with db.sessionmaker() as s:
        verify = await s.scalar(select(RunStep).where(RunStep.run_id == run_id, RunStep.key == "verify"))
    assert verify is not None and verify.output is not None
    out: dict[str, Any] = verify.output
    assert run.status == "completed", (run.status_reason, steps)
    assert out["tests_after"]["passed"] == 5 and out["tests_after"]["failed"] == 0
    assert out["bench_after"]["p50"] < out["bench_before"]["p50"]
    assert run.verification_label == "verified", out["reasons"]
    assert (
        events.count("sandbox.started") == events.count("sandbox.finished") == 4
    )  # baseline + patched, tests + bench
