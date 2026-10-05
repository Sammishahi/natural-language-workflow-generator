import httpx
import pytest

from app.engine.expressions import evaluate_condition, resolve_value
from app.errors import DataValidationError, ReferenceResolutionError, ToolError, WorkflowError
from app.models.workflow_schema import Condition
from app.tools import api_tools
from app.tools.registry import build_default_registry

registry = build_default_registry()


def test_registry_rejects_unknown_tool():
    with pytest.raises(WorkflowError):
        registry.execute("os_system", {"cmd": "dir"})


def test_calculator_and_safety():
    assert registry.execute("calculator", {"expression": "75000 * 0.18"}) == 13500
    with pytest.raises(DataValidationError):
        registry.execute("calculator", {"expression": "__import__('os').system('dir')"})


def test_concat_and_format_currency():
    assert registry.execute("concat_text", {"parts": ["Aarav", "Sharma"]}) == "Aarav Sharma"
    assert registry.execute("format_currency", {"amount": 75000}) == "₹75,000"


def test_validation_tools():
    with pytest.raises(DataValidationError):
        registry.execute("validate_required", {"values": {"email": ""}})
    with pytest.raises(DataValidationError):
        registry.execute("validate_email", {"value": "not-an-email"})
    with pytest.raises(DataValidationError):
        registry.execute("validate_number_range", {"value": 5, "min": 10})


def test_customer_not_found_is_not_retryable():
    with pytest.raises(ToolError) as info:
        registry.execute("get_customer", {"customer_id": "C999"})
    assert info.value.retryable is False


def test_http_get_blocks_unlisted_hosts():
    with pytest.raises(DataValidationError):
        registry.execute("http_get", {"url": "https://evil.example.com/data"})


def test_http_get_success_and_server_error(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/ok"):
            return httpx.Response(200, json={"hello": "world"})
        return httpx.Response(503)
    monkeypatch.setattr(api_tools, "_make_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    ok = registry.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/ok"})
    assert ok["data"] == {"hello": "world"}
    with pytest.raises(ToolError) as info:
        registry.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/bad"})
    assert info.value.retryable is True


def test_resolve_value_keeps_types_and_formats_text():
    ctx = {"order": {"amount": 75000, "items": [{"name": "Laptop"}]}}
    assert resolve_value("{{order.amount}}", ctx) == 75000
    assert resolve_value("Amount: {{order.amount}}", ctx) == "Amount: 75000"
    assert resolve_value("{{order.items.0.name}}", ctx) == "Laptop"
    with pytest.raises(ReferenceResolutionError):
        resolve_value("{{order.missing}}", ctx)


@pytest.mark.parametrize("left,op,right,expected", [
    (75000, ">", 50000, True), (50000, ">", 50000, False), (50000, ">=", 50000, True),
    ("12,000", "<", 50000, True), ("abc", "==", "abc", True), (5, "!=", 5, False),
    ("hello world", "contains", "world", True), ("a", "in", ["a", "b"], True),
])
def test_condition_operators(left, op, right, expected):
    assert evaluate_condition(Condition(left=left, operator=op, right=right), {}) is expected


def test_condition_exists_handles_missing_reference():
    assert evaluate_condition(Condition(left="{{nope.x}}", operator="exists"), {}) is False
    assert evaluate_condition(Condition(left="{{a.x}}", operator="exists"), {"a": {"x": 1}}) is True
