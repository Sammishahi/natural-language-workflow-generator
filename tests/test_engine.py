import pytest

from app.engine.workflow_engine import WorkflowEngine
from app.errors import WorkflowError
from app.models.run_state import Status
from app.models.workflow_schema import Workflow
from app.samples import SAMPLES
from app.tools import email_tool
from app.tools.registry import build_default_registry


@pytest.fixture
def engine():
    return WorkflowEngine(build_default_registry(), sleep=lambda _: None)


def load(key, mutate=None):
    data = SAMPLES[key]["workflow"]
    return Workflow.model_validate(mutate(data) if mutate else data)


def test_simple_workflow_completes(engine):
    run = engine.start(load("1"))
    assert run.state == Status.COMPLETED
    assert run.displays[0]["value"] == "aarav.sharma@example.com"


def test_transform_creates_full_name(engine):
    run = engine.start(load("3"))
    assert run.state == Status.COMPLETED
    assert run.context["full_name_text"] == "Priya Patel"
    assert run.context["customer_updated"]["full_name"] == "Priya Patel"


def test_high_value_order_pauses_then_approval_resumes(engine):
    run = engine.start(load("2"))
    assert run.state == Status.WAITING_FOR_APPROVAL
    assert "₹75,000" in run.pending_approval.message
    assert email_tool.OUTBOX == []                       # nothing sent before approval
    run = engine.submit_approval(run, True, "ok")
    assert run.state == Status.COMPLETED
    assert len(email_tool.OUTBOX) == 1
    assert run.steps["send_email_direct"].status == Status.SKIPPED


def test_rejection_stops_workflow(engine):
    run = engine.start(load("2"))
    run = engine.submit_approval(run, False, "too expensive")
    assert run.state == Status.REJECTED
    assert email_tool.OUTBOX == []
    assert run.steps["send_email_approved"].status == Status.SKIPPED
    assert "too expensive" in run.error


def test_low_value_order_skips_approval(engine):
    def low(data):
        data = {**data, "steps": [dict(s) for s in data["steps"]]}
        data["steps"][0]["params"] = {"order_id": "ORD-1002"}
        return data
    run = engine.start(load("2", low))
    assert run.state == Status.COMPLETED
    assert run.steps["manager_approval"].status == Status.SKIPPED
    assert run.steps["send_email_direct"].status == Status.COMPLETED


def test_cannot_approve_when_not_waiting(engine):
    run = engine.start(load("1"))
    with pytest.raises(WorkflowError):
        engine.submit_approval(run, True)


def test_retry_then_success(engine):
    run = engine.start(load("4"))
    assert run.state == Status.COMPLETED
    assert run.steps["fetch_user"].attempts == 2


def test_retry_exhausted_marks_failed(engine):
    run = engine.start(load("5"))
    assert run.state == Status.FAILED
    assert run.steps["fetch_user"].attempts == 3
    assert "503" in run.error
    assert run.steps["show_name"].status == Status.PENDING   # never executed


def test_validation_failure_is_not_retried_and_fails(engine):
    wf = Workflow.model_validate({"workflow_name": "t", "steps": [
        {"id": "c", "type": "tool", "tool": "get_customer", "params": {"customer_id": "C003"}, "output": "customer"},
        {"id": "v", "type": "validation", "tool": "validate_email", "params": {"value": "{{customer.email}}"},
         "on_error": {"strategy": "retry", "max_retries": 3}}]})
    run = engine.start(wf)
    assert run.state == Status.FAILED and run.steps["v"].attempts == 1


def test_continue_strategy_keeps_going(engine):
    wf = Workflow.model_validate({"workflow_name": "t", "steps": [
        {"id": "a", "type": "api", "tool": "mock_api", "params": {"endpoint": "users/1", "fail_times": 9},
         "on_error": {"strategy": "continue"}},
        {"id": "d", "type": "tool", "tool": "display", "params": {"label": "x", "value": "still running"}}]})
    run = engine.start(wf)
    assert run.state == Status.COMPLETED and run.steps["a"].status == Status.FAILED


def test_invalid_workflow_is_not_executed(engine):
    wf = Workflow.model_validate({"workflow_name": "t", "steps": [
        {"id": "x", "type": "tool", "tool": "delete_everything", "params": {}}]})
    with pytest.raises(WorkflowError):
        engine.start(wf)
