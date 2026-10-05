"""Controlled tool registry: the ONLY actions a workflow can execute."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.errors import DataValidationError, ToolError, WorkflowError


@dataclass
class ToolSpec:
    name: str
    category: str                 # api | tool | transform | validation
    description: str
    params: dict[str, str]        # param name -> short description
    required: list[str]
    func: Callable[[dict], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._reset_callbacks: list[Callable[[], None]] = []

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def on_reset(self, callback: Callable[[], None]) -> None:
        self._reset_callbacks.append(callback)

    def reset_state(self) -> None:
        """Called at the start of every run (clears mock counters, outbox...)."""
        for cb in self._reset_callbacks:
            cb()

    def get(self, name: str | None) -> ToolSpec | None:
        return self._tools.get(name or "")

    def names(self) -> list[str]:
        return sorted(self._tools)

    def execute(self, name: str, params: dict) -> Any:
        spec = self.get(name)
        if spec is None:
            raise WorkflowError(f"Tool '{name}' is not registered. Allowed: {self.names()}")
        missing = [p for p in spec.required if p not in params]
        if missing:
            raise WorkflowError(f"Tool '{name}' is missing required params: {missing}")
        try:
            return spec.func(params)
        except (ToolError, DataValidationError, WorkflowError):
            raise
        except Exception as exc:  # tool bugs must never crash the engine
            raise ToolError(f"Tool '{name}' crashed: {exc}", retryable=False) from exc

    def describe_for_prompt(self) -> str:
        """Human-readable catalog that is inserted into the LLM system prompt."""
        lines = []
        for spec in sorted(self._tools.values(), key=lambda s: (s.category, s.name)):
            params = ", ".join(f"{k} ({v})" for k, v in spec.params.items())
            lines.append(f'- {spec.name} [step type "{spec.category}"]: {spec.description} Params: {params}')
        return "\n".join(lines)


def build_default_registry() -> ToolRegistry:
    """Create the registry with all built-in tools."""
    from app.tools import api_tools, business_tools, calculator, data_tools, email_tool

    registry = ToolRegistry()
    for module in (calculator, api_tools, business_tools, data_tools, email_tool):
        module.register_tools(registry)
    return registry
