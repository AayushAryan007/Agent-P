"""ORM models. Schema rationale lives in docs/DATABASE_DESIGN.md; keep the two in sync."""

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid_utils.compat import uuid7

RUN_STATUSES = ("queued", "running", "waiting_approval", "completed", "failed", "cancelled")
STEP_STATUSES = ("pending", "running", "waiting_approval", "completed", "failed", "cancelled", "skipped")
TOOL_STATUSES = ("started", "completed", "failed", "denied")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "cancelled")
VERIFICATION_LABELS = ("verified", "partially_verified", "not_verified")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB,
        datetime: DateTime(timezone=True),
        uuid.UUID: UUID(as_uuid=True),
    }


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid7)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = pk()
    title: Mapped[str] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text)
    template_key: Mapped[str] = mapped_column(String(64))
    repo_source: Mapped[dict[str, Any]]
    default_model: Mapped[str] = mapped_column(String(128))
    limits: Mapped[dict[str, Any]]
    visibility: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'private')", name="visibility"),
        Index("ix_tasks_created_at", text("created_at DESC")),
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    status_reason: Mapped[str | None] = mapped_column(String(200))
    verification_label: Mapped[str | None] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    limits: Mapped[dict[str, Any]]
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    worker_id: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None]
    totals: Mapped[dict[str, Any]] = mapped_column(
        default=lambda: {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0}
    )
    queued_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint(_in("status", RUN_STATUSES), name="status"),
        CheckConstraint(
            f"verification_label IS NULL OR {_in('verification_label', VERIFICATION_LABELS)}",
            name="verification_label",
        ),
        Index("ix_runs_queue", "queued_at", postgresql_where=text("status = 'queued'")),
        Index("ix_runs_task", "task_id", text("queued_at DESC")),
        Index("ix_runs_finished_at", text("finished_at DESC")),
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    agent_role: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(120))
    depends_on: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    position: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict[str, Any] | None]
    output: Mapped[dict[str, Any] | None]
    error: Mapped[dict[str, Any] | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("run_id", "key", name="uq_run_steps_run_key"),
        CheckConstraint("kind IN ('agent', 'system', 'approval')", name="kind"),
        CheckConstraint(_in("status", STEP_STATUSES), name="status"),
    )


class ExecutionEvent(Base):
    """Append-only. The migration revokes UPDATE/DELETE and adds a guard trigger."""

    __tablename__ = "execution_events"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    sequence_number: Mapped[int] = mapped_column(BigInteger)
    schema_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    event_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    step_id: Mapped[uuid.UUID | None]
    tool_invocation_id: Mapped[uuid.UUID | None]
    parent_event_id: Mapped[uuid.UUID | None]
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)

    __table_args__ = (UniqueConstraint("run_id", "sequence_number", name="uq_events_run_seq"),)


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run_steps.id", ondelete="CASCADE"), index=True)
    llm_call_id: Mapped[uuid.UUID | None]
    tool_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    input: Mapped[dict[str, Any]]
    output_summary: Mapped[dict[str, Any] | None]
    output_truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[dict[str, Any] | None]
    trace_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(_in("status", TOOL_STATUSES), name="status"),
        Index("ix_tools_run_started", "run_id", "started_at"),
    )


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run_steps.id", ondelete="CASCADE"))
    attempt: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24))
    finish_reason: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    request_excerpt: Mapped[dict[str, Any] | None]
    response_excerpt: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (
        CheckConstraint("status IN ('ok', 'error', 'rate_limited', 'invalid_output')", name="status"),
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run_steps.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    summary: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(default=utcnow)
    decided_at: Mapped[datetime | None]
    decided_by: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_in("status", APPROVAL_STATUSES), name="status"),
        Index(
            "uq_approvals_one_pending_per_step",
            "step_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run_steps.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    inline_text: Mapped[str | None] = mapped_column(Text)
    inline_json: Mapped[dict[str, Any] | None]
    storage_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint(
            "kind IN ('patch', 'test_report', 'benchmark', 'review', 'report', 'log')", name="kind"
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = pk()
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    details: Mapped[dict[str, Any] | None]

    __table_args__ = (Index("ix_audit_occurred_at", text("occurred_at DESC")),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(SmallInteger)
    response_body: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(64))
