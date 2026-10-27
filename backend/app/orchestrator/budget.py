"""Per-run execution budgets (FR-17). Owned by the single worker executing the run."""

import time
from dataclasses import dataclass, field
from typing import Any


class BudgetExceeded(Exception):
    def __init__(self, kind: str, used: float, limit: float) -> None:
        super().__init__(f"{kind} budget exceeded ({used:g} / {limit:g})")
        self.kind = kind


@dataclass
class Budget:
    max_minutes: int
    max_llm_calls: int
    max_total_tokens: int
    max_tool_calls: int
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    _started: float = field(default_factory=time.monotonic)
    _paused_at: float | None = None
    _paused_total: float = 0.0

    @classmethod
    def from_limits(cls, limits: dict[str, Any], totals: dict[str, Any] | None = None) -> "Budget":
        b = cls(
            max_minutes=int(limits["max_minutes"]),
            max_llm_calls=int(limits["max_llm_calls"]),
            max_total_tokens=int(limits["max_total_tokens"]),
            max_tool_calls=int(limits["max_tool_calls"]),
        )
        for k in ("llm_calls", "input_tokens", "output_tokens", "tool_calls"):
            setattr(b, k, int((totals or {}).get(k, 0)))
        return b

    # Waiting for a human is not execution time; the approval step pauses the clock.
    def pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = time.monotonic()

    def resume(self) -> None:
        if self._paused_at is not None:
            self._paused_total += time.monotonic() - self._paused_at
            self._paused_at = None

    @property
    def elapsed_s(self) -> float:
        now = self._paused_at or time.monotonic()
        return now - self._started - self._paused_total

    def check_time(self) -> None:
        if self.elapsed_s > self.max_minutes * 60:
            raise BudgetExceeded("time", round(self.elapsed_s), self.max_minutes * 60)

    def check_llm(self) -> None:
        self.check_time()
        if self.llm_calls >= self.max_llm_calls:
            raise BudgetExceeded("llm_calls", self.llm_calls, self.max_llm_calls)
        if self.input_tokens + self.output_tokens >= self.max_total_tokens:
            raise BudgetExceeded("tokens", self.input_tokens + self.output_tokens, self.max_total_tokens)

    def check_tool(self) -> None:
        self.check_time()
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded("tool_calls", self.tool_calls, self.max_tool_calls)

    def record_llm(self, input_tokens: int, output_tokens: int) -> None:
        self.llm_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def totals(self) -> dict[str, int]:
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": self.tool_calls,
        }

    def warnings(self) -> list[tuple[str, float, float]]:
        """Budgets at or above 80%, for budget.warning events."""
        pairs = [
            ("llm_calls", self.llm_calls, self.max_llm_calls),
            ("tokens", self.input_tokens + self.output_tokens, self.max_total_tokens),
            ("tool_calls", self.tool_calls, self.max_tool_calls),
        ]
        return [(k, used, lim) for k, used, lim in pairs if lim and used / lim >= 0.8]
