"""One recorded model turn, with bounded retries and rate-limit fallback (ARCHITECTURE.md §6)."""

import asyncio

from uuid_utils.compat import uuid7

from app.events.store import append_event
from app.llm.base import Conversation, LLMError, LLMResponse, RateLimited, ToolSpec, TransientLLMError
from app.orchestrator.context import RunContext, StepInfo
from app.persistence.models import LLMCall

MAX_RATE_LIMIT_WAITS = 3
MAX_TRANSIENT_RETRIES = 2
MAX_BACKOFF_S = 30.0


async def llm_turn(
    ctx: RunContext, step: StepInfo, conv: Conversation, tools: list[ToolSpec], attempt: int
) -> tuple[LLMResponse, str]:
    """Run one model turn. Returns (response, llm_call_id). Every attempt is visible in the event log."""
    models = [ctx.model] + (
        [ctx.fallback_model] if ctx.fallback_model and ctx.fallback_model != ctx.model else []
    )
    model_idx = 0
    rate_waits = 0
    transient = 0
    while True:
        ctx.budget.check_llm()
        model = models[model_idx]
        started = await ctx.emit("llm.call_started", {"model": model, "attempt": attempt}, step_id=step.id)
        call_id = uuid7()
        try:
            resp = await ctx.provider.generate(conv, model, tools)
        except RateLimited as exc:
            await _record_failure(ctx, step, call_id, model, attempt, "rate_limited", str(exc), started.id)
            if model_idx + 1 < len(models):
                model_idx += 1
                await ctx.emit(
                    "retry.scheduled",
                    {
                        "target": "llm_call",
                        "attempt": attempt,
                        "delay_ms": 0,
                        "reason": f"rate limited; fallback to {models[model_idx]}",
                    },
                    step_id=step.id,
                )
                continue
            rate_waits += 1
            if rate_waits > MAX_RATE_LIMIT_WAITS:
                raise
            delay = min(exc.retry_after_s or 5.0 * 2 ** (rate_waits - 1), MAX_BACKOFF_S)
            await ctx.emit(
                "retry.scheduled",
                {
                    "target": "llm_call",
                    "attempt": attempt,
                    "delay_ms": int(delay * 1000),
                    "reason": "rate limited",
                },
                step_id=step.id,
            )
            await asyncio.sleep(delay)
            continue
        except TransientLLMError as exc:
            await _record_failure(ctx, step, call_id, model, attempt, "error", str(exc), started.id)
            transient += 1
            if transient > MAX_TRANSIENT_RETRIES:
                raise
            delay = 2.0 * transient
            await ctx.emit(
                "retry.scheduled",
                {
                    "target": "llm_call",
                    "attempt": attempt,
                    "delay_ms": int(delay * 1000),
                    "reason": str(exc)[:200],
                },
                step_id=step.id,
            )
            await asyncio.sleep(delay)
            continue
        except LLMError as exc:
            await _record_failure(ctx, step, call_id, model, attempt, "error", str(exc), started.id)
            raise

        ctx.budget.record_llm(resp.input_tokens, resp.output_tokens)
        async with ctx.db.sessionmaker() as s:
            s.add(
                LLMCall(
                    id=call_id,
                    run_id=ctx.run_id,
                    step_id=step.id,
                    attempt=attempt,
                    provider=ctx.provider.name,
                    model=resp.model,
                    status="ok",
                    finish_reason=resp.finish_reason,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                    latency_ms=resp.latency_ms,
                    response_excerpt={
                        "text": resp.text[:2000],
                        "tool_calls": [{"name": c.name, "arguments": c.arguments} for c in resp.tool_calls][
                            :10
                        ],
                    },
                )
            )
            await ctx.save_totals(s)
            await append_event(
                s,
                ctx.run_id,
                "llm.call_completed",
                {
                    "llm_call_id": str(call_id),
                    "model": resp.model,
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                    "latency_ms": resp.latency_ms,
                    "finish_reason": resp.finish_reason,
                    "tool_calls": [c.name for c in resp.tool_calls],
                },
                step_id=step.id,
                parent_event_id=started.id,
            )
            for kind, used, limit in ctx.budget.warnings():
                await append_event(
                    s,
                    ctx.run_id,
                    "budget.warning",
                    {"budget": kind, "used": used, "limit": limit},
                    step_id=step.id,
                )
            await s.commit()
        return resp, str(call_id)


async def _record_failure(
    ctx: RunContext,
    step: StepInfo,
    call_id: object,
    model: str,
    attempt: int,
    status: str,
    message: str,
    parent: object,
) -> None:
    async with ctx.db.sessionmaker() as s:
        s.add(
            LLMCall(
                id=call_id,
                run_id=ctx.run_id,
                step_id=step.id,
                attempt=attempt,
                provider=ctx.provider.name,
                model=model,
                status=status,
                response_excerpt={"error": message[:1000]},
            )
        )
        event = "llm.rate_limited" if status == "rate_limited" else "llm.call_failed"
        await append_event(
            s,
            ctx.run_id,
            event,
            {"llm_call_id": str(call_id), "model": model, "message": message[:500]},
            step_id=step.id,
            parent_event_id=parent,  # type: ignore[arg-type]
        )
        await s.commit()
