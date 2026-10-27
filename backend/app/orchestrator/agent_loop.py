"""Bounded agent loop: model turn → tool calls through the gate → ... → validated `submit_result`."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.definitions import AgentSpec
from app.llm.base import ToolResult, ToolSpec
from app.orchestrator.context import RunContext, StepInfo
from app.orchestrator.llm_turns import llm_turn
from app.orchestrator.tool_gate import invoke_tool
from app.tools.base import ToolContext, json_schema_for

SUBMIT = "submit_result"


class AgentFailed(Exception):
    pass


@dataclass
class AgentRun:
    output: BaseModel
    artifacts: list[uuid.UUID] = field(default_factory=list)
    turns: int = 0


def untrusted(label: str, content: str) -> str:
    """Wrap repository-derived text so the model treats it as data (prompt-injection hygiene)."""
    return f'<untrusted_data source="{label}">\n{content}\n</untrusted_data>'


async def run_agent(
    ctx: RunContext, step: StepInfo, spec: AgentSpec, user_prompt: str, tool_ctx: ToolContext
) -> AgentRun:
    tools = {t.name: t for t in spec.tools}
    specs: list[ToolSpec] = [t.spec() for t in spec.tools]
    specs.append(
        ToolSpec(
            SUBMIT,
            "Submit your final answer. Call exactly once, when done.",
            json_schema_for(spec.output_model),
        )
    )

    conv = ctx.provider.start(spec.system_prompt, user_prompt)
    artifacts: list[uuid.UUID] = []
    invalid = 0
    attempt = 1

    for turn in range(1, spec.max_turns + 1):
        if await ctx.cancel_requested():
            raise AgentFailed("cancelled")
        resp, llm_call_id = await llm_turn(ctx, step, conv, specs, attempt)
        if resp.text.strip():
            await ctx.emit(
                "agent.message", {"kind": "narration", "text": resp.text.strip()[:2000]}, step_id=step.id
            )

        if not resp.tool_calls:
            invalid += 1
            await _invalid(ctx, step, attempt, ["The response contained no tool call."], invalid, spec)
            attempt += 1
            ctx.provider.add_user_message(
                conv, "You must respond by calling a tool. Call submit_result when done."
            )
            continue

        results: list[ToolResult] = []
        for call in resp.tool_calls:
            if call.name == SUBMIT:
                try:
                    output = spec.output_model.model_validate(call.arguments)
                except ValidationError as exc:
                    errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()][:10]
                    invalid += 1
                    await _invalid(ctx, step, attempt, errors, invalid, spec)
                    attempt += 1
                    results.append(
                        ToolResult(call, {"error": "submit_result arguments are invalid", "details": errors})
                    )
                    continue
                return AgentRun(output=output, artifacts=artifacts, turns=turn)
            result, artifact_id = await invoke_tool(ctx, step, call, tools, llm_call_id, tool_ctx)
            if artifact_id:
                artifacts.append(artifact_id)
            results.append(result)
        ctx.provider.add_tool_results(conv, results)

    raise AgentFailed(f"{spec.key} did not submit a result within {spec.max_turns} turns")


async def _invalid(
    ctx: RunContext, step: StepInfo, attempt: int, errors: list[str], count: int, spec: AgentSpec
) -> None:
    await ctx.emit("agent.output_invalid", {"attempt": attempt, "validation_errors": errors}, step_id=step.id)
    if count > spec.max_invalid_outputs:
        raise AgentFailed(f"{spec.key} produced invalid output {count} times: {'; '.join(errors)[:300]}")
    await ctx.emit(
        "retry.scheduled",
        {"target": "step_output", "attempt": attempt + 1, "delay_ms": 0, "reason": "invalid output"},
        step_id=step.id,
    )


def output_summary(data: dict[str, Any], limit: int = 600) -> dict[str, Any]:
    """Short version of a step output for events; long strings are clipped."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = v if len(v) <= limit else v[:limit] + "…"
        elif isinstance(v, list):
            out[k] = v[:8]
        else:
            out[k] = v
    return out
