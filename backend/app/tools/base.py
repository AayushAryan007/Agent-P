"""Typed tools. A model's tool call is a *request*; the gate (orchestrator.tool_gate) decides whether it runs.

Tools here are pure with respect to the platform: they read the run workspace and return bounded
output. They never touch the database, the network, or anything outside their `ToolContext`.
"""

import copy
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.llm.base import ToolSpec

MAX_MODEL_CONTENT_CHARS = 16_000


class ToolError(Exception):
    """Expected failure the model can learn from (bad path, no match, ...). Reported back to the model."""


class PolicyViolation(ToolError):
    """The request is outside what this run is authorized to do. Recorded as `tool.denied`."""


@dataclass(frozen=True)
class ToolContext:
    repo_root: Path  # the run's working copy; tools must stay inside it


@dataclass(frozen=True)
class ArtifactDraft:
    kind: str
    name: str
    content_type: str
    text: str | None = None
    json: dict[str, Any] | None = None


@dataclass
class ToolOutput:
    summary: dict[str, Any]  # small, for events and the UI
    model_content: dict[str, Any]  # what the model receives (bounded)
    truncated: bool = False
    artifact: ArtifactDraft | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    run: Callable[[ToolContext, Any], Awaitable[ToolOutput]]
    runs_in: str = "worker"
    tags: frozenset[str] = field(default_factory=frozenset)

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, json_schema_for(self.args_model))


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema with $refs inlined and titles dropped (portable across providers)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    result: dict[str, Any] = resolve(schema)
    return result


def bound_text(text: str, limit: int = MAX_MODEL_CONTENT_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n… [truncated {len(text) - limit} characters]", True
