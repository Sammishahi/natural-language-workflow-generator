"""Run logging: every event is stored on the run (shown in the UI) and echoed to the console."""
import logging
from datetime import datetime
from typing import Optional

from app.models.run_state import LogEntry, WorkflowRun

logger = logging.getLogger("workflow")


def log_event(run: WorkflowRun, level: str, message: str, step_id: Optional[str] = None) -> None:
    entry = LogEntry(
        timestamp=datetime.now().strftime("%H:%M:%S"),
        level=level.upper(),
        step_id=step_id,
        message=message,
    )
    run.logs.append(entry)
    logger.log(getattr(logging, entry.level, logging.INFO), "[%s] %s", step_id or "-", message)
