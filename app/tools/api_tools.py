"""API tools: a real public API (allow-listed) and a deterministic mock API for failure demos."""
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.errors import DataValidationError, ToolError
from app.tools.registry import ToolRegistry, ToolSpec


def _make_client() -> httpx.Client:
    """Separate function so tests can replace it with a mock transport."""
    return httpx.Client(timeout=10, follow_redirects=False)


def http_get(params: dict) -> dict:
    url = str(params["url"])
    parsed = urlparse(url)
    allowed = get_settings().allowed_api_hosts
    if parsed.scheme != "https" or parsed.hostname not in allowed:
        raise DataValidationError(f"URL not allowed. Only https hosts {list(allowed)} can be called.")
    try:
        with _make_client() as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        raise ToolError(f"API request failed: {exc}") from exc
    if response.status_code >= 500:
        raise ToolError(f"API returned HTTP {response.status_code}")
    if response.status_code >= 400:
        raise ToolError(f"API returned HTTP {response.status_code}", retryable=False)
    try:
        data = response.json()
    except ValueError as exc:
        raise ToolError("API did not return valid JSON", retryable=False) from exc
    return {"status": response.status_code, "data": data}


_MOCK_DATA = {
    "users/1": {"id": 1, "name": "Leanne Graham", "email": "leanne@example.com"},
    "users/2": {"id": 2, "name": "Ervin Howell", "email": "ervin@example.com"},
}


def register_tools(registry: ToolRegistry) -> None:
    calls: dict[str, int] = {}
    registry.on_reset(calls.clear)

    def mock_api(params: dict) -> dict:
        """Deterministic fake API: fails the first `fail_times` calls, then succeeds."""
        endpoint = str(params["endpoint"])
        calls[endpoint] = calls.get(endpoint, 0) + 1
        fail_times = int(params.get("fail_times", 0))
        if calls[endpoint] <= fail_times:
            raise ToolError(f"Mock API '{endpoint}' returned HTTP 503 (call {calls[endpoint]})")
        if endpoint not in _MOCK_DATA:
            raise ToolError(f"Mock API endpoint '{endpoint}' not found (404)", retryable=False)
        return {"status": 200, "data": _MOCK_DATA[endpoint]}

    registry.register(ToolSpec(
        name="http_get", category="api",
        description="HTTP GET to a public JSON API (only jsonplaceholder.typicode.com or dummyjson.com). "
                    "Returns {status, data}.",
        params={"url": "full https URL, e.g. https://jsonplaceholder.typicode.com/users/1"},
        required=["url"], func=http_get,
    ))
    registry.register(ToolSpec(
        name="mock_api", category="api",
        description="Fake internal API for demos. Endpoints: 'users/1', 'users/2'. "
                    "Use fail_times to simulate temporary failures. Returns {status, data}.",
        params={"endpoint": "e.g. users/1", "fail_times": "optional int, number of initial failing calls"},
        required=["endpoint"], func=mock_api,
    ))
