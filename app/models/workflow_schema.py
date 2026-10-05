"""Pydantic models describing a workflow. The LLM must produce JSON matching these models."""
from __future__ import annotations

import heapq
import re
from collections import defaultdict
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class StepType(str, Enum):
    API = "api"
    TOOL = "tool"
    TRANSFORM = "transform"
    VALIDATION = "validation"
    CONDITION = "condition"
    HUMAN_APPROVAL = "human_approval"


TOOL_STEP_TYPES = {StepType.API, StepType.TOOL, StepType.TRANSFORM, StepType.VALIDATION}

Operator = Literal["==", "!=", ">", ">=", "<", "<=", "contains", "in", "exists"]


class Condition(BaseModel):
    model_config = ConfigDict(extra="ignore")
    left: Any
    operator: Operator
    right: Any = None


class ErrorHandling(BaseModel):
    model_config = ConfigDict(extra="ignore")
    strategy: Literal["fail", "retry", "continue"] = "fail"
    max_retries: int = Field(default=0, ge=0, le=5)
    retry_delay_seconds: float = Field(default=0.5, ge=0, le=10)

    @model_validator(mode="after")
    def _default_retries(self) -> "ErrorHandling":
        if self.strategy == "retry" and self.max_retries == 0:
            self.max_retries = 2
        return self


class Step(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    description: str = ""
    type: StepType
    tool: Optional[str] = None                       # for api/tool/transform/validation steps
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    output: Optional[str] = None                     # name used in {{output.field}} references
    condition: Optional[Condition] = None            # for condition steps
    if_true: list[str] = Field(default_factory=list)   # step ids that run when condition is true
    if_false: list[str] = Field(default_factory=list)  # step ids that run when condition is false
    message: Optional[str] = None                    # for human_approval steps
    approver_role: str = "manager"
    on_error: ErrorHandling = Field(default_factory=ErrorHandling)

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"id '{v}' must contain only letters, digits, underscores")
        return v

    @field_validator("output")
    @classmethod
    def _check_output(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not ID_PATTERN.match(v):
            raise ValueError(f"output '{v}' must contain only letters, digits, underscores")
        return v

    @model_validator(mode="after")
    def _check_step_shape(self) -> "Step":
        if self.output is None:
            self.output = self.id
        if self.type in TOOL_STEP_TYPES and not self.tool:
            raise ValueError(f"step '{self.id}' of type '{self.type.value}' needs a 'tool'")
        if self.type == StepType.CONDITION and self.condition is None:
            raise ValueError(f"condition step '{self.id}' needs a 'condition'")
        if self.type == StepType.HUMAN_APPROVAL and not self.message:
            raise ValueError(f"human_approval step '{self.id}' needs a 'message'")
        return self


class Workflow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workflow_name: str
    description: str = ""
    steps: list[Step] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def _check_graph(self) -> "Workflow":
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        outputs = [s.output for s in self.steps]
        if len(outputs) != len(set(outputs)):
            raise ValueError("step output names must be unique")
        known = set(ids)
        for s in self.steps:
            for ref in s.depends_on + s.if_true + s.if_false:
                if ref not in known:
                    raise ValueError(f"step '{s.id}' references unknown step id '{ref}'")
            if s.id in s.depends_on or s.id in s.if_true or s.id in s.if_false:
                raise ValueError(f"step '{s.id}' cannot reference itself")
            if set(s.if_true) & set(s.if_false):
                raise ValueError(f"step '{s.id}' lists the same step in both if_true and if_false")
        return self

    def get_step(self, step_id: str) -> Step:
        return next(s for s in self.steps if s.id == step_id)

    def execution_order(self) -> list[str]:
        """Topological order (respects depends_on, keeps list order when possible)."""
        index = {s.id: i for i, s in enumerate(self.steps)}
        indegree = {s.id: len(set(s.depends_on)) for s in self.steps}
        children: dict[str, list[str]] = defaultdict(list)
        for s in self.steps:
            for dep in set(s.depends_on):
                children[dep].append(s.id)
        heap = [index[i] for i, d in indegree.items() if d == 0]
        heapq.heapify(heap)
        order: list[str] = []
        while heap:
            current = self.steps[heapq.heappop(heap)].id
            order.append(current)
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    heapq.heappush(heap, index[child])
        if len(order) != len(self.steps):
            stuck = [i for i, d in indegree.items() if d > 0]
            raise ValueError(f"circular dependency among steps: {stuck}")
        return order


def format_pydantic_error(exc: ValidationError) -> list[str]:
    """Turn a Pydantic error into short readable strings (also fed back to the LLM for repair)."""
    messages = []
    for err in exc.errors():
        location = ".".join(str(p) for p in err["loc"]) or "workflow"
        messages.append(f"{location}: {err['msg']}")
    return messages
