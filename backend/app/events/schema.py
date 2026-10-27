"""Execution event schema v1 (docs/API_SPECIFICATION.md §5)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = 1

# Terminal workflow events; once one is streamed the SSE connection can end.
TERMINAL_EVENT_TYPES = frozenset({"workflow.completed", "workflow.failed", "workflow.cancelled"})

# Payloads are capped; bulky data belongs in artifacts and is referenced by id.
MAX_PAYLOAD_BYTES = 32 * 1024

NOTIFY_CHANNEL = "run_events"


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    schema_version: int
    run_id: uuid.UUID
    sequence_number: int
    occurred_at: datetime
    event_type: str
    step_id: uuid.UUID | None
    tool_invocation_id: uuid.UUID | None
    parent_event_id: uuid.UUID | None
    payload: dict[str, Any]
