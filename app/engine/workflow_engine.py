"""Workflow engine: runs validated workflows step by step.

Supports retries, conditional branches, human approval (pause/resume) and clear states.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from app.engine.expressions import evaluate_condition, resolve_value
from app.engine.validator import validate_workflow
from app.errors import DataValidationError, ReferenceResolutionError, ToolError, WorkflowError
from app.models.run_state import ApprovalRequest, Status, StepRecord, WorkflowRun
from app.models.workflow_schema import Step, StepType, Workflow
from app.tools.registry import ToolRegistry
from app.utils.logger import log_event


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class WorkflowEngine:
    def __init__(self, registry: ToolRegistry, sleep: Callable[[float], None] = time.sleep) -> None:
        self.registry = registry
        self._sleep = sleep

    # ------------------------------------------------------------------ public API
    def start(self, workflow: Workflow) -> WorkflowRun:
        """Validate, then run until finished or until human approval is needed."""
        report = validate_workflow(workflow, self.registry)
        if not report.valid:
            raise WorkflowError("Workflow is invalid: " + "; ".join(report.errors))
        wf = report.workflow
        run = WorkflowRun(
            workflow=wf,
            order=wf.execution_order(),
            steps={s.id: StepRecord(step_id=s.id) for s in wf.steps},
        )
        self.registry.reset_state()
        run.state = Status.RUNNING
        log_event(run, "info", f"Workflow '{wf.workflow_name}' started with {len(wf.steps)} steps")
        self._advance(run)
        return run

    def submit_approval(self, run: WorkflowRun, approved: bool, comment: str = "") -> WorkflowRun:
        """Resume (approve) or stop (reject) a run that is WAITING_FOR_APPROVAL."""
        if run.state != Status.WAITING_FOR_APPROVAL or run.pending_approval is None:
            raise WorkflowError("This run is not waiting for approval")
        request = run.pending_approval
        step = run.workflow.get_step(request.step_id)
        record = run.steps[step.id]
        run.pending_approval = None
        decision = {"approved": approved, "approver_role": request.approver_role, "comment": comment}

        if approved:
            record.status, record.output = Status.COMPLETED, decision
            run.context[step.output] = decision
            run.cursor += 1
            run.state = Status.RUNNING
            log_event(run, "info", f"Approved by {request.approver_role}. Resuming workflow", step.id)
            self._advance(run)
        else:
            record.status, record.output = Status.REJECTED, decision
            run.state = Status.REJECTED
            run.error = f"Rejected by {request.approver_role} at step '{step.id}'" + (f": {comment}" if comment else "")
            for remaining in run.order[run.cursor + 1:]:
                if run.steps[remaining].status == Status.PENDING:
                    run.steps[remaining].status = Status.SKIPPED
                    run.steps[remaining].note = "not executed (workflow rejected)"
            run.finished_at = _now()
            log_event(run, "warning", run.error, step.id)
        return run

    # ------------------------------------------------------------------ internals
    def _advance(self, run: WorkflowRun) -> None:
        wf = run.workflow
        while run.cursor < len(run.order):
            step = wf.get_step(run.order[run.cursor])
            record = run.steps[step.id]

            # skip steps in a branch that was not taken (or that depend on a skipped step)
            if step.id in run.skipped or any(d in run.skipped for d in step.depends_on):
                run.skipped.add(step.id)
                record.status, record.note = Status.SKIPPED, "branch not taken"
                log_event(run, "info", "Skipped (branch not taken)", step.id)
                run.cursor += 1
                continue

            record.status = Status.RUNNING
            try:
                if step.type == StepType.CONDITION:
                    self._run_condition(run, step)
                elif step.type == StepType.HUMAN_APPROVAL:
                    self._request_approval(run, step)
                    return  # pause here until submit_approval()
                else:
                    self._run_tool_step(run, step)
            except (WorkflowError, ReferenceResolutionError) as exc:
                self._fail(run, step, str(exc))
                return
            except _StepFailed as exc:
                self._fail(run, step, str(exc))
                return
            run.cursor += 1

        run.state = Status.COMPLETED
        run.finished_at = _now()
        log_event(run, "info", "Workflow completed")

    def _run_condition(self, run: WorkflowRun, step: Step) -> None:
        result = evaluate_condition(step.condition, run.context)
        run.context[step.output] = result
        not_taken = step.if_false if result else step.if_true
        run.skipped.update(not_taken)
        record = run.steps[step.id]
        record.status, record.output, record.attempts = Status.COMPLETED, result, 1
        log_event(run, "info", f"Condition evaluated to {result}; skipping {not_taken or 'nothing'}", step.id)

    def _request_approval(self, run: WorkflowRun, step: Step) -> None:
        message = str(resolve_value(step.message, run.context))
        run.pending_approval = ApprovalRequest(step_id=step.id, message=message, approver_role=step.approver_role)
        run.steps[step.id].status = Status.WAITING_FOR_APPROVAL
        run.state = Status.WAITING_FOR_APPROVAL
        log_event(run, "info", f"Waiting for {step.approver_role} approval: {message}", step.id)

    def _run_tool_step(self, run: WorkflowRun, step: Step) -> None:
        record = run.steps[step.id]
        handling = step.on_error
        max_attempts = 1 + (handling.max_retries if handling.strategy == "retry" else 0)
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            record.attempts = attempt
            try:
                params = resolve_value(step.params, run.context)
                result = self.registry.execute(step.tool, params)
            except (DataValidationError, ToolError) as exc:
                last_error = str(exc)
                retryable = isinstance(exc, ToolError) and exc.retryable
                if retryable and attempt < max_attempts:
                    log_event(run, "warning", f"Attempt {attempt}/{max_attempts} failed: {last_error}. "
                                              f"Retrying in {handling.retry_delay_seconds}s", step.id)
                    self._sleep(handling.retry_delay_seconds)
                    continue
                break
            else:
                record.status, record.output = Status.COMPLETED, result
                run.context[step.output] = result
                if step.tool == "display":
                    run.displays.append(result)
                log_event(run, "info", f"Completed ({step.tool}) after {attempt} attempt(s)", step.id)
                return

        # all attempts failed
        record.error = last_error
        if handling.strategy == "continue":
            record.status = Status.FAILED
            record.note = "failed but workflow continued (on_error=continue)"
            run.context[step.output] = {"error": last_error}
            log_event(run, "warning", f"Failed but continuing: {last_error}", step.id)
            return
        raise _StepFailed(last_error)

    def _fail(self, run: WorkflowRun, step: Step, message: str) -> None:
        record = run.steps[step.id]
        record.status, record.error = Status.FAILED, message
        run.state = Status.FAILED
        run.error = f"Step '{step.id}' failed: {message}"
        run.finished_at = _now()
        log_event(run, "error", run.error, step.id)


class _StepFailed(Exception):
    """Internal: a tool step failed for good (after any retries)."""
