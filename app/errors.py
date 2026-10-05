"""Custom exceptions used across the project."""


class WorkflowError(Exception):
    """Problem with the workflow itself (bad reference, unknown tool, wrong state...)."""


class ReferenceResolutionError(WorkflowError):
    """A {{reference}} could not be resolved from the workflow context."""


class ToolError(Exception):
    """A tool failed while running. `retryable=True` means retrying may help (e.g. API timeout)."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class DataValidationError(Exception):
    """Input data is invalid (bad email, missing field...). Never retried."""


class LLMError(Exception):
    """Problem talking to the cloud LLM API."""
