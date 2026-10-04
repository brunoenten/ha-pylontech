"""Fixtures for Pylontech US tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def fake_responses(cmd: str) -> str:
    """Return a canned console response for a command."""
    base = cmd.split()[0]
    if base in ("pwr", "info", "bat", "stat", "time"):
        if base == "info" and cmd != "info":
            return load_fixture("info_sample.txt").replace("Device address      : 1",
                                                         f"Device address      : {cmd.split()[1]}")
        if base == "time" and len(cmd.split()) > 1:
            return f"{cmd}\r\n@\r\nCommand completed successfully\r\n$$\r\n\rpylon>"
        return load_fixture(f"{base}_sample.txt")
    return f"{cmd}\r\nInvalid command\r\n$$\r\n\rpylon>"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_console() -> Generator:
    with patch(
        "custom_components.pylontech_us.console.PylontechConsole.command",
        side_effect=fake_responses,
        autospec=False,
    ) as mock, patch(
        "custom_components.pylontech_us.console.PylontechConsole.close",
        return_value=None,
    ):
        yield mock
