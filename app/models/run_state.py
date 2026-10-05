"""Runtime state of one workflow execution."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.workflow_schema import Workflow


class Status(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"   # only used for steps


class LogEntry(BaseModel):
    timestamp: str
    level: str
    step_id: Optional[str] = None
    message: str


class StepRecord(BaseModel):
    step_id: str
    status: Status = Status.PENDING
    attempts: int = 0
    output: Any = None
    error: Optional[str] = None
    note: str = ""


class ApprovalRequest(BaseModel):
    step_id: str
    message: str
    approver_role: str = "manager"


class WorkflowRun(BaseModel):
    workflow: Workflow
    order: list[str]
    state: Status = Status.PENDING
    cursor: int = 0                                   # index in `order` of the next step to run
    steps: dict[str, StepRecord] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)   # step outputs, used by {{references}}
    skipped: set[str] = Field(default_factory=set)
    displays: list[dict[str, Any]] = Field(default_factory=list)  # results shown to the user
    pending_approval: Optional[ApprovalRequest] = None
    error: Optional[str] = None
    logs: list[LogEntry] = Field(default_factory=list)
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None
