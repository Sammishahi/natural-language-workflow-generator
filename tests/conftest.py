import pytest

from app.tools import email_tool


@pytest.fixture(autouse=True)
def clean_outbox():
    email_tool.OUTBOX.clear()
    yield
    email_tool.OUTBOX.clear()
