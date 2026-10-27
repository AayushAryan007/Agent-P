"""DAG scheduler for one run: start every step whose dependencies are done, up to a concurrency limit."""

import asyncio
import time
from typing import Any

import structlog

from app.llm.base import LLMError
from app.orchestrator.agent_loop import AgentFailed, output_summary
from app.orchestrator.budget import BudgetExceeded
from app.orchestrator.context import RunContext
from app.orchestrator.steps import STEPS, StepFailed, StepSkipped

log = structlog.get_logger(__name__)

DONE = frozenset({"completed", "skipped"})


class RunFailed(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


async def _run_step(ctx: RunContext, key: str) -> None:
    info = ctx.steps[key]
    if info.status == "completed":  # already done (not expected in MVP; kept for safety)
        return
    await ctx.set_step_status(key, "running", "step.started", {"attempt": 1}, attempt=1)
    t0 = time.perf_counter()
    try:
        output = await STEPS[key](ctx, info)
    except StepSkipped as exc:
        ctx.skipped.add(key)
        await ctx.set_step_status(key, "skipped", "step.skipped", {"reason": str(exc)})
        return
    except asyncio.CancelledError:
        raise
    except BudgetExceeded as exc:
        await _fail_step(ctx, key, "budget", str(exc))
        raise RunFailed(f"budget_exceeded:{exc.kind}", str(exc)) from exc
    except (StepFailed, AgentFailed, LLMError) as exc:
        await _fail_step(ctx, key, type(exc).__name__, str(exc))
        raise RunFailed(f"step_failed:{key}", str(exc)) from exc
    except Exception as exc:
        log.exception("step.crashed", step=key)
        await _fail_step(ctx, key, "internal_error", f"{type(exc).__name__}: {exc}")
        raise RunFailed(f"step_failed:{key}", f"internal error in {key}") from exc

    ctx.outputs[key] = output
    duration_ms = int((time.perf_counter() - t0) * 1000)
    await ctx.set_step_status(
        key,
        "completed",
        "step.completed",
        {"duration_ms": duration_ms, "output_summary": output_summary(output)},
        output=output,
    )


async def _fail_step(ctx: RunContext, key: str, error_type: str, message: str) -> None:
    if ctx.steps[key].status in ("running", "waiting_approval"):
        await ctx.set_step_status(
            key,
            "failed",
            "step.failed",
            {"error_type": error_type, "message": message[:1000], "retryable": False},
            error={"type": error_type, "message": message[:2000]},
        )


async def execute(ctx: RunContext) -> dict[str, Any]:
    """Run all steps. Returns the report step output. Raises RunFailed or CancelledError."""
    running: dict[str, asyncio.Task[None]] = {}
    try:
        while True:
            done_keys = {k for k, s in ctx.steps.items() if s.status in DONE}
            ready = [
                k
                for k, s in ctx.steps.items()
                if s.status == "pending" and k not in running and all(d in done_keys for d in s.depends_on)
            ]
            for key in ready[: max(0, ctx.settings.step_concurrency - len(running))]:
                running[key] = asyncio.create_task(_run_step(ctx, key), name=f"step:{key}")
            if not running:
                break
            finished, _ = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
            for task in finished:
                key = next(k for k, t in running.items() if t is task)
                del running[key]
                task.result()  # re-raises RunFailed
    finally:
        for t in running.values():
            t.cancel()
        if running:
            await asyncio.gather(*running.values(), return_exceptions=True)

    pending = [k for k, s in ctx.steps.items() if s.status not in DONE]
    if pending:
        raise RunFailed("deadlock", f"steps could not be scheduled: {pending}")
    return ctx.outputs["report"]
