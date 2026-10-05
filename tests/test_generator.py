"""LLM tests use a fake HTTP transport - no real API key or internet needed."""
import json

import httpx
import pytest

from app.config import Settings
from app.errors import LLMError
from app.llm.workflow_generator import WorkflowGenerator, extract_json
from app.samples import SAMPLES
from app.tools.registry import build_default_registry

SETTINGS = Settings("test-key", "https://llm.example/v1", "test-model", 10, 3, ("jsonplaceholder.typicode.com",))
GOOD = json.dumps(SAMPLES["1"]["workflow"])


def make_generator(replies, status=200, settings=SETTINGS):
    calls = {"n": 0, "bodies": []}

    def handler(request):
        calls["bodies"].append(json.loads(request.content))
        reply = replies[min(calls["n"], len(replies) - 1)]
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, text="error")
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WorkflowGenerator(build_default_registry(), settings, client), calls


def test_extract_json_handles_markdown_fences():
    assert extract_json("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_valid_reply_is_accepted():
    gen, calls = make_generator([GOOD])
    result = gen.generate("get customer C001 email")
    assert result.workflow is not None and result.attempts == 1 and calls["n"] == 1
    assert calls["bodies"][0]["messages"][0]["role"] == "system"


def test_invalid_reply_is_repaired_with_feedback():
    bad = json.dumps({"workflow_name": "x", "steps": [{"id": "a", "type": "tool", "tool": "run_python", "params": {}}]})
    gen, calls = make_generator([bad, GOOD])
    result = gen.generate("anything")
    assert result.workflow is not None and result.attempts == 2
    assert "not registered" in calls["bodies"][1]["messages"][-1]["content"]


def test_non_json_reply_fails_after_max_attempts():
    gen, calls = make_generator(["sorry, I cannot do that"])
    result = gen.generate("anything")
    assert result.workflow is None and calls["n"] == 3 and "Could not generate" in result.error


def test_missing_api_key_gives_clear_error():
    no_key = Settings("", "https://llm.example/v1", "m", 10, 3, ())
    gen, _ = make_generator([GOOD], settings=no_key)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        gen.generate("x")


def test_http_401_gives_clear_error():
    gen, _ = make_generator([GOOD], status=401)
    with pytest.raises(LLMError, match="API key"):
        gen.generate("x")
