"""Deterministic scripted provider for automated tests. Never used in production.

Each scripted turn is a list of tool calls (or an exception to raise). The
provider records what the agent sent so tests can assert on prompts and tool
results.
"""

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.llm.base import Conversation, LLMResponse, ToolCall, ToolResult, ToolSpec

Turn = list[tuple[str, dict[str, Any]]] | Exception
TurnFn = Callable[[Conversation, list[ToolSpec]], Turn]


@dataclass
class ScriptedProvider:
    """`scripts` maps an agent's system-prompt marker (e.g. "[role:debugging]") to its turns."""

    scripts: dict[str, list[Turn | TurnFn]]
    name: str = "scripted"
    calls: list[dict[str, Any]] = field(default_factory=list)
    _ids: "itertools.count[int]" = field(default_factory=itertools.count)

    def start(self, system: str, user: str) -> Conversation:
        return Conversation(system=system, messages=[{"role": "user", "text": user}])

    async def generate(self, conv: Conversation, model: str, tools: list[ToolSpec]) -> LLMResponse:
        key = next((k for k in self.scripts if k in conv.system), None)
        if key is None or not self.scripts[key]:
            raise AssertionError(f"no scripted turn left for system prompt {conv.system[:60]!r}")
        step = self.scripts[key].pop(0)
        turn = step(conv, tools) if callable(step) else step
        self.calls.append({"role": key, "model": model, "tools": [t.name for t in tools]})
        if isinstance(turn, Exception):
            raise turn
        calls = [ToolCall(id=f"c{next(self._ids)}", name=n, arguments=a) for n, a in turn]
        conv.messages.append({"role": "model", "calls": [(c.name, c.arguments) for c in calls]})
        return LLMResponse(
            model=model,
            text="",
            tool_calls=calls,
            input_tokens=100,
            output_tokens=20,
            finish_reason="STOP",
            latency_ms=5,
        )

    def add_user_message(self, conv: Conversation, text: str) -> None:
        conv.messages.append({"role": "user", "text": text})

    def add_tool_results(self, conv: Conversation, results: list[ToolResult]) -> None:
        conv.messages.append({"role": "tool", "results": [(r.call.name, r.content) for r in results]})
