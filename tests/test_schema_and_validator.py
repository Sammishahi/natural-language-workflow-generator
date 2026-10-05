import pytest
from pydantic import ValidationError

from app.engine.validator import validate_workflow
from app.models.workflow_schema import Workflow
from app.samples import SAMPLES
from app.tools.registry import build_default_registry

registry = build_default_registry()


def wf(steps):
    return Workflow.model_validate({"workflow_name": "t", "steps": steps})


def test_all_samples_are_valid():
    for key, sample in SAMPLES.items():
        report = validate_workflow(Workflow.model_validate(sample["workflow"]), registry)
        assert report.valid, f"sample {key}: {report.errors}"


def test_duplicate_ids_rejected():
    with pytest.raises(ValidationError):
        wf([{"id": "a", "type": "tool", "tool": "get_customer", "params": {"customer_id": "C001"}},
            {"id": "a", "type": "tool", "tool": "get_customer", "params": {"customer_id": "C001"}}])


def test_condition_step_requires_condition():
    with pytest.raises(ValidationError):
        wf([{"id": "c", "type": "condition"}])


def test_human_approval_requires_message():
    with pytest.raises(ValidationError):
        wf([{"id": "h", "type": "human_approval"}])


def test_unknown_tool_is_rejected():
    report = validate_workflow(wf([{"id": "x", "type": "tool", "tool": "run_python", "params": {"code": "1"}}]), registry)
    assert not report.valid and "not registered" in report.errors[0]


def test_missing_required_param_is_rejected():
    report = validate_workflow(wf([{"id": "x", "type": "tool", "tool": "get_customer", "params": {}}]), registry)
    assert not report.valid and "missing required params" in report.errors[0]


def test_unknown_reference_is_rejected():
    report = validate_workflow(wf([{"id": "x", "type": "tool", "tool": "display",
                                    "params": {"label": "a", "value": "{{nothing.here}}"}}]), registry)
    assert not report.valid and "does not match any step output" in report.errors[0]


def test_missing_dependency_is_added_automatically():
    report = validate_workflow(wf([
        {"id": "a", "type": "tool", "tool": "get_customer", "params": {"customer_id": "C001"}, "output": "cust"},
        {"id": "b", "type": "tool", "tool": "display", "params": {"label": "e", "value": "{{cust.email}}"}},
    ]), registry)
    assert report.valid and report.workflow.get_step("b").depends_on == ["a"]


def test_cycle_is_rejected():
    report = validate_workflow(wf([
        {"id": "a", "type": "tool", "tool": "display", "params": {"label": "x", "value": "1"}, "depends_on": ["b"]},
        {"id": "b", "type": "tool", "tool": "display", "params": {"label": "x", "value": "1"}, "depends_on": ["a"]},
    ]), registry)
    assert not report.valid and "circular" in report.errors[0]


def test_wrong_step_type_is_auto_corrected():
    report = validate_workflow(wf([{"id": "x", "type": "tool", "tool": "mock_api", "params": {"endpoint": "users/1"}}]), registry)
    assert report.valid and report.workflow.steps[0].type.value == "api" and report.warnings
