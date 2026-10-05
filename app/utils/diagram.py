"""Builds a Graphviz DOT string of a workflow (rendered by st.graphviz_chart in the browser)."""
from typing import Optional

from app.models.workflow_schema import StepType, Workflow

_COLORS = {"COMPLETED": "#c8f7c5", "FAILED": "#f8c6c6", "REJECTED": "#f8c6c6", "SKIPPED": "#e0e0e0",
           "WAITING_FOR_APPROVAL": "#ffe9a8", "RUNNING": "#cfe4ff", "PENDING": "#ffffff"}
_SHAPES = {StepType.CONDITION: "diamond", StepType.HUMAN_APPROVAL: "octagon"}


def workflow_to_dot(workflow: Workflow, statuses: Optional[dict[str, str]] = None) -> str:
    statuses = statuses or {}
    lines = ["digraph W {", "rankdir=TB;", 'node [fontname="Helvetica", fontsize=10, style=filled];']
    for step in workflow.steps:
        label = f"{step.id}\\n[{step.type.value}{': ' + step.tool if step.tool else ''}]".replace('"', "'")
        color = _COLORS.get(statuses.get(step.id, "PENDING"), "#ffffff")
        shape = _SHAPES.get(step.type, "box")
        lines.append(f'"{step.id}" [label="{label}", shape={shape}, fillcolor="{color}"];')
    for step in workflow.steps:
        for dep in step.depends_on:
            style = ""
            dep_step = workflow.get_step(dep)
            if dep_step.type == StepType.CONDITION:
                style = ' [label="true"]' if step.id in dep_step.if_true else ' [label="false"]'
            lines.append(f'"{dep}" -> "{step.id}"{style};')
    lines.append("}")
    return "\n".join(lines)
