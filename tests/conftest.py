"""Fixtures for Pylontech US tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.pylontech_us.console import ConsoleError

FIXTURES = Path(__file__).parent / "fixtures"
COMMANDS = ("pwr", "info", "bat", "stat", "time")


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def make_responder(pwr_fixture: str = "pwr.txt") -> Callable[[str], str]:
    """Return a fake `PylontechConsole.command` answering from captured output."""

    def respond(cmd: str) -> str:
        base, *args = cmd.split()
        if base not in COMMANDS:
            return f"{cmd}\r\n@\r\nInvalid command\r\n$$\r\n\rpylon>"
        if base == "time" and args:
            return f"{cmd}\r\n@\r\nCommand completed successfully\r\n$$\r\n\rpylon>"
        if base == "pwr":
            return load_fixture(pwr_fixture)
        if base in ("info", "stat") and args and args[0] != "1":
            raise ConsoleError(f"Timeout waiting for prompt after {cmd!r}")
        if base == "bat" and args and args[0] != "1":
            return load_fixture("bat_slave.txt")
        return load_fixture(f"{base}.txt")

    return respond


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def pwr_fixture() -> str:
    return "pwr.txt"


@pytest.fixture
def mock_console(pwr_fixture: str) -> Generator:
    with (
        patch(
            "custom_components.pylontech_us.console.PylontechConsole.command",
            side_effect=make_responder(pwr_fixture),
        ) as mock,
        patch("custom_components.pylontech_us.console.PylontechConsole.close", return_value=None),
    ):
        yield mock
