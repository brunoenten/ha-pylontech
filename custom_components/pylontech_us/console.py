"""Async client for the Pylontech US RS232 console."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re

import serialx

_LOGGER = logging.getLogger(__name__)

_PROMPT_RE = re.compile(rb"pylon\w*>\s*$")
_CONTINUE_MARKER = b"Press [Enter] to be continued"
_MAX_RESPONSE = 256 * 1024


class ConsoleError(Exception):
    """Raised when the console cannot be reached or does not answer."""


class PylontechConsole:
    """Command/response client for the battery console port."""

    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 5.0) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> None:
        """Open the serial port and synchronise with the prompt."""
        async with self._lock:
            await self._connect()

    async def _connect(self) -> None:
        if self._writer is not None:
            return
        _LOGGER.debug("Opening %s at %s baud", self.port, self.baud_rate)
        try:
            self._reader, self._writer = await serialx.open_serial_connection(
                url=self.port, baudrate=self.baud_rate
            )
        except (OSError, serialx.SerialException) as err:
            raise ConsoleError(f"Cannot open {self.port}: {err}") from err
        try:
            await self._sync()
        except ConsoleError:
            await self._close()
            raise

    async def _sync(self) -> None:
        """Send an empty line until the prompt shows up."""
        for _ in range(3):
            self._drain()
            self._write(b"\r")
            try:
                await self._read_until_prompt(timeout=min(self.timeout, 2.0))
            except ConsoleError:
                continue
            return
        raise ConsoleError(f"No console prompt on {self.port}")

    async def close(self) -> None:
        async with self._lock:
            await self._close()

    async def _close(self) -> None:
        writer, self._writer, self._reader = self._writer, None, None
        if writer is None:
            return
        writer.close()
        with contextlib.suppress(OSError, serialx.SerialException):
            await writer.wait_closed()

    def _write(self, data: bytes) -> None:
        assert self._writer is not None
        self._writer.write(data)

    def _drain(self) -> None:
        assert self._reader is not None
        buffer = getattr(self._reader, "_buffer", None)
        if buffer is not None:
            buffer.clear()

    async def _read_until_prompt(self, timeout: float, echo: bytes | None = None) -> bytes:
        """Read until the prompt; with `echo`, ignore prompts before the command echo."""
        assert self._reader is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        data = bytearray()
        scanned = 0
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ConsoleError(f"Timeout waiting for prompt, got {bytes(data[-200:])!r}")
            try:
                chunk = await asyncio.wait_for(self._reader.read(4096), remaining)
            except TimeoutError:
                continue
            if not chunk:
                raise ConsoleError("Serial port closed")
            data += chunk
            if len(data) > _MAX_RESPONSE:
                raise ConsoleError("Response too large")
            idx = data.find(_CONTINUE_MARKER, scanned)
            if idx >= 0:
                scanned = idx + len(_CONTINUE_MARKER)
                self._write(b"\r")
                deadline = loop.time() + timeout
                continue
            scanned = max(scanned, len(data) - len(_CONTINUE_MARKER))
            if not _PROMPT_RE.search(bytes(data[-64:])):
                continue
            if echo is None:
                return bytes(data)
            start = data.find(echo)
            if start < 0 and b"$$" not in data:
                continue
            return bytes(data[max(start, 0) :])

    async def command(self, cmd: str, timeout: float | None = None) -> str:
        """Send a command and return the raw response text."""
        async with self._lock:
            for attempt in (1, 2):
                try:
                    await self._connect()
                    self._drain()
                    self._write(cmd.encode("ascii") + b"\r")
                    raw = await self._read_until_prompt(
                        timeout or self.timeout, echo=cmd.encode("ascii")
                    )
                    _LOGGER.debug("Response to %r: %r", cmd, raw)
                    return raw.decode("ascii", errors="replace")
                except (ConsoleError, OSError, serialx.SerialException) as err:
                    _LOGGER.debug("Command %r failed (attempt %s): %s", cmd, attempt, err)
                    await self._close()
                    if attempt == 2:
                        if isinstance(err, ConsoleError):
                            raise
                        raise ConsoleError(str(err)) from err
            raise AssertionError("unreachable")
