"""Central configuration. All secrets come from environment variables / .env."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout: float
    max_generation_attempts: int
    allowed_api_hosts: tuple


def get_settings() -> Settings:
    """Read settings fresh each call (makes tests and .env edits easy)."""
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip(),
        llm_model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip(),
        llm_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_generation_attempts=int(os.getenv("MAX_GENERATION_ATTEMPTS", "3")),
        # The http_get tool may ONLY call these hosts (security allow-list).
        allowed_api_hosts=("jsonplaceholder.typicode.com", "dummyjson.com"),
    )
