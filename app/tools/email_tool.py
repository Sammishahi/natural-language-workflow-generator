"""Mock email sender: nothing is really sent, messages are recorded in OUTBOX."""
import re
import uuid

from app.errors import DataValidationError
from app.tools.registry import ToolRegistry, ToolSpec

OUTBOX: list[dict] = []
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def send_email(params: dict) -> dict:
    to = str(params["to"]).strip()
    if not _EMAIL.match(to):
        raise DataValidationError(f"Invalid recipient email address: '{to}'")
    message = {
        "status": "sent (mock)",
        "message_id": uuid.uuid4().hex[:8],
        "to": to,
        "subject": str(params["subject"]),
        "body": str(params["body"]),
    }
    OUTBOX.append(message)
    return message


def register_tools(registry: ToolRegistry) -> None:
    registry.on_reset(OUTBOX.clear)
    registry.register(ToolSpec(
        name="send_email", category="tool",
        description="Sends an email (MOCK: recorded, not really sent). Returns {status, message_id, to, subject, body}.",
        params={"to": "recipient email", "subject": "subject line", "body": "email body"},
        required=["to", "subject", "body"], func=send_email,
    ))
