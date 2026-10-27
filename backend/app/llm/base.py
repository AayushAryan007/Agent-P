"""Provider-neutral LLM interface (ADR-0002).

Agents talk to `LLMProvider` only. A provider owns the message history format
(`Conversation`), so provider-specific details such as Gemini thought
signatures are preserved without leaking into orchestration code.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (object)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call: ToolCall
    content: dict[str, Any]  # what the model sees; already bounded and redacted


@dataclass
class LLMResponse:
    model: str
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    finish_reason: str | None
    latency_ms: int


class LLMError(Exception):
    """Non-retryable provider failure (bad request, auth, safety block, ...)."""


class TransientLLMError(LLMError):
    """Retryable failure (5xx, timeout, connection reset)."""


class RateLimited(TransientLLMError):
    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


@dataclass
class Conversation:
    """Opaque, provider-owned message history. `messages` must only be touched by the provider."""

    system: str
    messages: list[Any] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str

    def start(self, system: str, user: str) -> Conversation: ...

    async def generate(self, conv: Conversation, model: str, tools: list[ToolSpec]) -> LLMResponse:
        """Run one model turn. The model MUST answer with tool calls (forced function calling)."""
        ...

    def add_tool_results(self, conv: Conversation, results: list[ToolResult]) -> None: ...

    def add_user_message(self, conv: Conversation, text: str) -> None: ...
