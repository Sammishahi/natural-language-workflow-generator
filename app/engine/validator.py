"""Registry-aware validation + normalisation of a workflow BEFORE it is executed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.engine.expressions import find_references
from app.models.workflow_schema import TOOL_STEP_TYPES, StepType, Workflow
from app.tools.registry import ToolRegistry


@dataclass
class ValidationReport:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    workflow: Optional[Workflow] = None   # normalised copy (only when valid)


def validate_workflow(workflow: Workflow, registry: ToolRegistry) -> ValidationReport:
    wf = workflow.model_copy(deep=True)
    errors: list[str] = []
    warnings: list[str] = []
    by_id = {s.id: s for s in wf.steps}

    # 1) Only registered tools, with required params present
    for step in wf.steps:
        if step.type not in TOOL_STEP_TYPES:
            continue
        spec = registry.get(step.tool)
        if spec is None:
            errors.append(f"Step '{step.id}': tool '{step.tool}' is not registered. "
                          f"Allowed tools: {registry.names()}")
            continue
        if step.type.value != spec.category:
            warnings.append(f"Step '{step.id}': type corrected from '{step.type.value}' to '{spec.category}'")
            step.type = StepType(spec.category)
        missing = [p for p in spec.required if p not in step.params]
        if missing:
            errors.append(f"Step '{step.id}': tool '{spec.name}' is missing required params {missing}")

    # 2) Branch steps must wait for their condition step
    for step in wf.steps:
        if step.type == StepType.CONDITION:
            for branch_id in step.if_true + step.if_false:
                if step.id not in by_id[branch_id].depends_on:
                    by_id[branch_id].depends_on.append(step.id)
        elif step.if_true or step.if_false:
            warnings.append(f"Step '{step.id}': if_true/if_false are ignored on non-condition steps")
            step.if_true, step.if_false = [], []

    # 3) {{references}} must point to a real output; add missing dependencies automatically
    output_owner = {s.output: s.id for s in wf.steps}
    for step in wf.steps:
        refs = find_references(step.params) | find_references(step.condition) | find_references(step.message)
        for root in sorted(refs):
            owner = output_owner.get(root)
            if owner is None:
                errors.append(f"Step '{step.id}': reference '{{{{{root}}}}}' does not match any step output. "
                              f"Available outputs: {sorted(output_owner)}")
            elif owner == step.id:
                errors.append(f"Step '{step.id}' references its own output")
            elif owner not in step.depends_on:
                step.depends_on.append(owner)
                warnings.append(f"Step '{step.id}': added missing dependency on '{owner}'")

    # 4) No circular dependencies
    try:
        wf.execution_order()
    except ValueError as exc:
        errors.append(str(exc))

    return ValidationReport(valid=not errors, errors=errors, warnings=warnings,
                            workflow=wf if not errors else None)
