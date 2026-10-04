"""Tests for the console client using a fake serial stream."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from custom_components.pylontech_us.console import ConsoleError, PylontechConsole

from .conftest import load_fixture

PROMPT = b"\r\n\rpylon>"


class FakeWriter:
    """Writer that feeds scripted replies into a StreamReader."""

    def __init__(self, reader: asyncio.StreamReader, replies: dict[bytes, list[bytes]]) -> None:
        self.reader = reader
        self.replies = replies
        self.written: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.written.append(data)
        for chunk in self.replies.get(data, []):
            asyncio.get_running_loop().call_soon(self.reader.feed_data, chunk)

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


def _patch(replies: dict[bytes, list[bytes]]):
    holder: dict[str, FakeWriter] = {}

    async def fake_open(**_kwargs):
        reader = asyncio.StreamReader()
        holder["writer"] = FakeWriter(reader, replies)
        return reader, holder["writer"]

    return patch("serialx.open_serial_connection", side_effect=fake_open), holder


async def test_command_reads_until_prompt() -> None:
    pwr = load_fixture("pwr_sample.txt").encode()
    half = len(pwr) // 2
    patcher, _ = _patch({b"\r": [PROMPT], b"pwr\r": [pwr[:half], pwr[half:]]})
    with patcher:
        console = PylontechConsole("/dev/null")
        raw = await console.command("pwr")
    assert "Absent" in raw
    assert raw.rstrip().endswith("pylon>")


async def test_command_handles_pagination() -> None:
    page1 = b"log\r\n@\r\nline 1\r\nPress [Enter] to be continued,other key to exit"
    page2 = b"\r\nline 2\r\nCommand completed successfully\r\n$$" + PROMPT
    patcher, holder = _patch({b"\r": [PROMPT], b"log\r": [page1]})
    with patcher:
        console = PylontechConsole("/dev/null")
        await console.connect()
        holder["writer"].replies[b"\r"] = [page2]
        raw = await console.command("log")
    assert "line 1" in raw and "line 2" in raw


async def test_no_prompt_raises() -> None:
    patcher, _ = _patch({})
    with patcher, pytest.raises(ConsoleError):
        await PylontechConsole("/dev/null", timeout=0.05).command("pwr")
