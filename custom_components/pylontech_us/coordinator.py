"""Data update coordinator for the Pylontech US console."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .console import ConsoleError, PylontechConsole
from .const import (
    CONF_BAUD_RATE,
    CONF_CELL_POLL_EVERY,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_STAT_POLL_EVERY,
    DEFAULT_BAUD_RATE,
    DEFAULT_CELL_POLL_EVERY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STAT_POLL_EVERY,
    DOMAIN,
)
from .models import CellData, ModuleData, ModuleInfo, StackData, StatData
from .parser import (
    ParseError,
    format_time_command,
    parse_bat,
    parse_info,
    parse_pwr,
    parse_stat,
    parse_time,
)

_LOGGER = logging.getLogger(__name__)

type PylontechConfigEntry = ConfigEntry[PylontechCoordinator]


class PylontechCoordinator(DataUpdateCoordinator[StackData]):
    """Poll the console and assemble a `StackData` snapshot."""

    config_entry: PylontechConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PylontechConfigEntry) -> None:
        options = entry.options
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.console = PylontechConsole(
            entry.data[CONF_SERIAL_PORT],
            entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE),
        )
        self.cell_poll_every: int = options.get(CONF_CELL_POLL_EVERY, DEFAULT_CELL_POLL_EVERY)
        self.stat_poll_every: int = options.get(CONF_STAT_POLL_EVERY, DEFAULT_STAT_POLL_EVERY)
        self.master: ModuleInfo | None = None
        self.raw: dict[str, str] = {}
        self._cycle = 0
        self._module_info: dict[int, ModuleInfo | None] = {}
        self._cells: dict[int, list[CellData]] = {}
        self._stats: dict[int, StatData] = {}
        self._bms_time: datetime | None = None

    async def _command(self, cmd: str) -> str:
        raw = await self.console.command(cmd)
        self.raw[cmd] = raw
        return raw

    async def _async_setup(self) -> None:
        try:
            self.master = parse_info(await self._command("info"))
        except (ConsoleError, ParseError) as err:
            raise UpdateFailed(f"Cannot read battery info: {err}") from err

    async def _module_command(self, cmd: str, address: int) -> str:
        """Run `cmd N`, falling back to plain `cmd` for the master module."""
        raw = await self._command(f"{cmd} {address}")
        if self.master and address == self.master.address and "Invalid" in raw:
            raw = await self._command(cmd)
        return raw

    async def _async_update_data(self) -> StackData:
        try:
            return await self._poll()
        except ConsoleError as err:
            raise UpdateFailed(f"Console error: {err}") from err
        except ParseError as err:
            raise UpdateFailed(f"Unexpected console output: {err}") from err

    async def _poll(self) -> StackData:
        assert self.master is not None
        rows = parse_pwr(await self._command("pwr"))
        poll_cells = self.cell_poll_every > 0 and self._cycle % self.cell_poll_every == 0
        poll_stat = self.stat_poll_every > 0 and self._cycle % self.stat_poll_every == 0

        modules: dict[int, ModuleData] = {}
        for address, row in rows.items():
            if address not in self._module_info:
                self._module_info[address] = await self._read_info(address)
            if poll_cells or address not in self._cells:
                try:
                    self._cells[address] = parse_bat(await self._module_command("bat", address))
                except ParseError as err:
                    _LOGGER.debug("No cell data for module %s: %s", address, err)
                    self._cells.setdefault(address, [])
            if poll_stat or address not in self._stats:
                self._stats[address] = parse_stat(await self._module_command("stat", address))
            modules[address] = ModuleData(
                address=address,
                power=row,
                info=self._module_info[address],
                cells=self._cells.get(address, []),
                stat=self._stats.get(address),
            )

        if poll_stat or self._bms_time is None:
            self._bms_time = parse_time(await self._command("time"))

        self._cycle += 1
        return StackData(master=self.master, modules=modules, bms_time=self._bms_time)

    async def _read_info(self, address: int) -> ModuleInfo | None:
        if self.master and address == self.master.address:
            return self.master
        try:
            return parse_info(await self._command(f"info {address}"))
        except ParseError:
            _LOGGER.debug("No info for module %s", address)
            return None

    async def async_sync_time(self) -> None:
        """Set the BMS clock to Home Assistant's local time."""
        now = dt_util.now().replace(tzinfo=None)
        try:
            await self.console.command(format_time_command(now))
        except ConsoleError as err:
            raise UpdateFailed(f"Cannot set BMS time: {err}") from err
        self._bms_time = None
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.console.close()
