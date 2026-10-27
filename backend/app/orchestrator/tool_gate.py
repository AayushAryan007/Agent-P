"""The tool gate: a model's tool request becomes an execution only after validation (SECURITY_MODEL.md §4.2).

allowlist → argument schema → budget → execute with timeout → bound + redact output → record.
Every outcome, including denials, is a ToolInvocation row and an event.
"""

import asyncio
import time
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import update
from uuid_utils.compat import uuid7

from app.events.store import append_event
from app.llm.base import ToolCall, ToolResult
from app.orchestrator.budget import BudgetExceeded
from app.orchestrator.context import RunContext, StepInfo
from app.persistence.models import ToolInvocation, utcnow
from app.security.redaction import redact
from app.tools.base import PolicyViolation, Tool, ToolContext, ToolError

TOOL_TIMEOUT_S = 30
MAX_ARG_CHARS = 2000


def sanitize_args(args: dict[str, Any]) -> dict[str, Any]:
    def trim(v: Any) -> Any:
        if isinstance(v, str) and len(v) > MAX_ARG_CHARS:
            return v[:MAX_ARG_CHARS] + f"… [+{len(v) - MAX_ARG_CHARS} chars]"
        if isinstance(v, dict):
            return {k: trim(x) for k, x in v.items()}
        if isinstance(v, list):
            return [trim(x) for x in v[:50]]
        return v

    result: dict[str, Any] = redact(trim(args))
    return result


async def invoke_tool(
    ctx: RunContext,
    step: StepInfo,
    call: ToolCall,
    tools: dict[str, Tool],
    llm_call_id: str | None,
    tool_ctx: ToolContext,
) -> tuple[ToolResult, uuid.UUID | None]:
    """Returns (result for the model, artifact id if the tool produced one)."""
    inv_id = uuid7()
    safe_args = sanitize_args(call.arguments)
    llm_id = uuid.UUID(llm_call_id) if llm_call_id else None

    tool = tools.get(call.name)
    if tool is None:
        await _deny(
            ctx,
            step,
            inv_id,
            call.name,
            safe_args,
            llm_id,
            "not_allowed",
            f"tool {call.name!r} is not available to this agent",
        )
        return ToolResult(
            call, {"error": f"Tool {call.name!r} is not available. Use one of: {sorted(tools)}"}
        ), None
    try:
        args = tool.args_model.model_validate(call.arguments)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()][:10]
        await _deny(ctx, step, inv_id, call.name, safe_args, llm_id, "invalid_args", "; ".join(errors))
        return ToolResult(call, {"error": "Invalid arguments", "details": errors}), None
    try:
        ctx.budget.check_tool()
    except BudgetExceeded:
        await _deny(ctx, step, inv_id, call.name, safe_args, llm_id, "budget", "tool call budget exhausted")
        raise

    ctx.budget.tool_calls += 1
    async with ctx.db.sessionmaker() as s:
        s.add(
            ToolInvocation(
                id=inv_id,
                run_id=ctx.run_id,
                step_id=step.id,
                llm_call_id=llm_id,
                tool_name=tool.name,
                status="started",
                input=safe_args,
                trace_id=inv_id.hex,
            )
        )
        await ctx.save_totals(s)
        started = await append_event(
            s,
            ctx.run_id,
            "tool.started",
            {"tool_name": tool.name, "input": safe_args},
            step_id=step.id,
            tool_invocation_id=inv_id,
        )
        await s.commit()

    t0 = time.perf_counter()
    try:
        out = await asyncio.wait_for(tool.run(tool_ctx, args), timeout=TOOL_TIMEOUT_S)
    except PolicyViolation as exc:
        await _finish(
            ctx,
            step,
            inv_id,
            "denied",
            started.id,
            t0,
            error={"reason": "policy", "message": str(exc)},
            event="tool.denied",
            extra={"tool_name": tool.name, "reason": f"policy: {exc}"},
        )
        return ToolResult(call, {"error": f"Denied by policy: {exc}"}), None
    except ToolError as exc:
        await _finish(
            ctx,
            step,
            inv_id,
            "failed",
            started.id,
            t0,
            error={"reason": "tool_error", "message": str(exc)},
            event="tool.failed",
            extra={"error_type": "tool_error", "message": str(exc)},
        )
        return ToolResult(call, {"error": str(exc)}), None
    except TimeoutError:
        await _finish(
            ctx,
            step,
            inv_id,
            "failed",
            started.id,
            t0,
            error={"reason": "timeout", "message": f"exceeded {TOOL_TIMEOUT_S}s"},
            event="tool.failed",
            extra={"error_type": "timeout", "message": f"exceeded {TOOL_TIMEOUT_S}s"},
        )
        return ToolResult(call, {"error": f"Tool timed out after {TOOL_TIMEOUT_S}s"}), None

    artifact_id = await ctx.store_artifact(step.key, out.artifact) if out.artifact else None
    summary = {**out.summary, **({"artifact_id": str(artifact_id)} if artifact_id else {})}
    await _finish(
        ctx,
        step,
        inv_id,
        "completed",
        started.id,
        t0,
        event="tool.completed",
        extra={"output_summary": summary, "truncated": out.truncated},
        output_summary=summary,
        truncated=out.truncated,
    )
    return ToolResult(call, redact(out.model_content)), artifact_id


async def _deny(
    ctx: RunContext,
    step: StepInfo,
    inv_id: uuid.UUID,
    name: str,
    args: dict[str, Any],
    llm_id: uuid.UUID | None,
    reason: str,
    message: str,
) -> None:
    async with ctx.db.sessionmaker() as s:
        s.add(
            ToolInvocation(
                id=inv_id,
                run_id=ctx.run_id,
                step_id=step.id,
                llm_call_id=llm_id,
                tool_name=name[:64],
                status="denied",
                input=args,
                error={"reason": reason, "message": message},
                finished_at=utcnow(),
                duration_ms=0,
                trace_id=inv_id.hex,
            )
        )
        await append_event(
            s,
            ctx.run_id,
            "tool.denied",
            {"tool_name": name[:64], "reason": f"{reason}: {message}"[:500], "input": args},
            step_id=step.id,
            tool_invocation_id=inv_id,
        )
        await s.commit()


async def _finish(
    ctx: RunContext,
    step: StepInfo,
    inv_id: uuid.UUID,
    status: str,
    parent: uuid.UUID,
    t0: float,
    *,
    event: str,
    extra: dict[str, Any],
    error: dict[str, Any] | None = None,
    output_summary: dict[str, Any] | None = None,
    truncated: bool = False,
) -> None:
    duration_ms = int((time.perf_counter() - t0) * 1000)
    async with ctx.db.sessionmaker() as s:
        await s.execute(
            update(ToolInvocation)
            .where(ToolInvocation.id == inv_id)
            .values(
                status=status,
                finished_at=utcnow(),
                duration_ms=duration_ms,
                output_summary=output_summary,
                output_truncated=truncated,
                error=error,
            )
        )
        await append_event(
            s,
            ctx.run_id,
            event,
            {**extra, "duration_ms": duration_ms},
            step_id=step.id,
            tool_invocation_id=inv_id,
            parent_event_id=parent,
        )
        await s.commit()
