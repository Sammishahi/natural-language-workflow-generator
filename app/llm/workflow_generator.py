"""Natural language -> validated Workflow, using a cloud LLM (OpenAI-compatible chat API)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.engine.validator import ValidationReport, validate_workflow
from app.errors import LLMError
from app.llm.prompts import build_system_prompt
from app.models.workflow_schema import Workflow, format_pydantic_error
from app.tools.registry import ToolRegistry


@dataclass
class GenerationResult:
    workflow: Optional[Workflow]          # normalised + valid workflow (None on failure)
    raw_json: str                         # last raw LLM output
    report: Optional[ValidationReport]
    attempts: int
    error: Optional[str] = None


def extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in ```json fences or added extra text."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the reply")
    return json.loads(cleaned[start:end + 1])


class WorkflowGenerator:
    def __init__(self, registry: ToolRegistry, settings: Optional[Settings] = None,
                 client: Optional[httpx.Client] = None) -> None:
        self.registry = registry
        self.settings = settings or get_settings()
        self._client = client

    # -------------------------------------------------------------- LLM call
    def _chat(self, messages: list[dict]) -> str:
        s = self.settings
        if not s.llm_api_key:
            raise LLMError("LLM_API_KEY is not set. Copy .env.example to .env and add your key.")
        url = s.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {s.llm_api_key}", "Content-Type": "application/json"}
        client = self._client or httpx.Client(timeout=s.llm_timeout)
        response = None
        try:
            for json_mode in (True, False):   # some providers reject response_format -> retry without it
                payload = {"model": s.llm_model, "messages": messages, "temperature": 0}
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 400 and json_mode:
                    continue
                break
        except httpx.RequestError as exc:
            raise LLMError(f"Could not reach the LLM API: {exc}") from exc
        finally:
            if self._client is None:
                client.close()

        if response.status_code in (401, 403):
            raise LLMError("The LLM API rejected the API key (401/403). Check LLM_API_KEY.")
        if response.status_code == 429:
            raise LLMError("LLM API rate limit reached (429). Wait a minute and try again.")
        if response.status_code != 200:
            raise LLMError(f"LLM API error {response.status_code}: {response.text[:300]}")
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Unexpected LLM API response format: {response.text[:300]}") from exc

    # -------------------------------------------------------------- main entry
    def generate(self, requirement: str) -> GenerationResult:
        requirement = requirement.strip()
        if not requirement:
            return GenerationResult(None, "", None, 0, "Please enter a requirement first.")

        messages = [
            {"role": "system", "content": build_system_prompt(self.registry.describe_for_prompt())},
            {"role": "user", "content": f"Requirement: {requirement}"},
        ]
        raw, report, problems = "", None, []
        attempts = 0
        for attempts in range(1, self.settings.max_generation_attempts + 1):
            raw = self._chat(messages)
            problems = []
            try:
                workflow = Workflow.model_validate(extract_json(raw))
                report = validate_workflow(workflow, self.registry)
                if report.valid:
                    return GenerationResult(report.workflow, raw, report, attempts)
                problems = report.errors
            except (ValueError, ValidationError) as exc:   # JSONDecodeError is a ValueError
                problems = format_pydantic_error(exc) if isinstance(exc, ValidationError) else [str(exc)]

            # self-repair: show the model its mistakes and ask for a corrected JSON
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                             "The JSON is invalid. Fix these problems and return the full corrected JSON only:\n- "
                             + "\n- ".join(problems)})

        return GenerationResult(None, raw, report, attempts,
                                "Could not generate a valid workflow: " + "; ".join(problems))
