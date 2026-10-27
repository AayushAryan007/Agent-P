"""Request/response models for /api/v1 (docs/API_SPECIFICATION.md §3)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.events.schema import EventOut

# ADR-0003: public github.com HTTPS repositories only; no credentials, no other hosts.
GITHUB_URL_PATTERN = r"^https://github\.com/[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}?(\.git)?/?$"

RunStatus = Literal["queued", "running", "waiting_approval", "completed", "failed", "cancelled"]
StepStatus = Literal["pending", "running", "waiting_approval", "completed", "failed", "cancelled", "skipped"]
VerificationLabel = Literal["verified", "partially_verified", "not_verified"]


class Limits(BaseModel):
    max_minutes: int = Field(ge=1)
    max_llm_calls: int = Field(ge=1)
    max_total_tokens: int = Field(ge=1)
    max_tool_calls: int = Field(ge=1)


class BundledSource(BaseModel):
    kind: Literal["bundled"]
    key: Annotated[str, StringConstraints(max_length=64)]


class GithubSource(BaseModel):
    kind: Literal["github"]
    url: Annotated[str, StringConstraints(max_length=200, pattern=GITHUB_URL_PATTERN)]


RepoSource = Annotated[BundledSource | GithubSource, Field(discriminator="kind")]


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=4000)]
    template_key: Annotated[str, StringConstraints(max_length=64)]
    repo_source: RepoSource
    model: Annotated[str, StringConstraints(max_length=128)]
    limits: Limits
    visibility: Literal["public", "private"] = "public"


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    goal: str
    template_key: str
    repo_source: dict[str, str]
    model: str
    limits: Limits
    visibility: Literal["public", "private"]
    created_at: datetime


class RunTotals(BaseModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0


class RunListItem(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_title: str
    status: RunStatus
    status_reason: str | None
    verification_label: VerificationLabel | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    totals: RunTotals


class RunStepOut(BaseModel):
    id: uuid.UUID
    key: str
    kind: Literal["agent", "system", "approval"]
    role: str | None
    title: str
    depends_on: list[str]
    status: StepStatus
    attempt: int
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunListItem):
    model: str
    limits: Limits
    steps: list[RunStepOut]
    last_sequence: int


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


class EventsPage(BaseModel):
    items: list[EventOut]
    next_after_seq: int | None


class MetricsSummary(BaseModel):
    window: str
    runs_total: int
    runs_by_status: dict[str, int]
    success_rate: float | None
    avg_duration_ms: float | None
    p95_duration_ms: float | None
    total_tokens: int
    pending_approvals: int
    recent_failures: list[RunListItem]


class StepDefinitionOut(BaseModel):
    id: str
    key: str
    kind: str
    role: str | None
    title: str
    depends_on: list[str]


class ToolInfoOut(BaseModel):
    name: str
    description: str
    runs_in: Literal["api_worker", "sandbox"]


class TemplateOut(BaseModel):
    key: str
    title: str
    description: str
    steps: list[StepDefinitionOut]
    tools: list[ToolInfoOut]


class BundledRepoOut(BaseModel):
    key: str
    title: str
    description: str


class ModelInfo(BaseModel):
    id: str
    role: Literal["default", "fallback", "available"]


class ProviderOut(BaseModel):
    name: str
    configured: bool
    models: list[ModelInfo]


class MetaOut(BaseModel):
    templates: list[TemplateOut]
    bundled_repos: list[BundledRepoOut]
    providers: list[ProviderOut]
    limits_default: Limits
    limits_max: Limits


class MeOut(BaseModel):
    role: Literal["operator", "anonymous"]
    # Synchronizer CSRF token for the SPA to echo in X-CSRF-Token; only present for operators.
    csrf_token: str | None = None


class LoginRequest(BaseModel):
    token: Annotated[str, StringConstraints(min_length=1, max_length=512)]
