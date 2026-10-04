"""Config flow for the Pylontech US console integration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import serialx
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .console import ConsoleError, PylontechConsole
from .const import (
    BAUD_RATES,
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
from .models import ModuleInfo
from .parser import ParseError, parse_info

_LOGGER = logging.getLogger(__name__)


async def validate_port(port: str, baud_rate: int) -> ModuleInfo:
    """Connect to the console and read the master module info."""
    console = PylontechConsole(port, baud_rate)
    try:
        return parse_info(await console.command("info"))
    finally:
        await console.close()


def _serial_by_id(device: str) -> str:
    by_id = Path("/dev/serial/by-id")
    if by_id.is_dir():
        real = os.path.realpath(device)
        for link in by_id.iterdir():
            if os.path.realpath(link) == real:
                return str(link)
    return device


def _list_ports() -> list[SelectOptionDict]:
    options: list[SelectOptionDict] = []
    for info in serialx.list_serial_ports():
        path = _serial_by_id(info.device)
        details = " - ".join(p for p in (info.product, info.manufacturer, info.serial_number) if p)
        label = f"{path} ({details})" if details else path
        options.append(SelectOptionDict(value=path, label=label))
    return sorted(options, key=lambda o: o["value"])


class PylontechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pylontech US."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_SERIAL_PORT]
            baud_rate = int(user_input[CONF_BAUD_RATE])
            self._async_abort_entries_match({CONF_SERIAL_PORT: port})
            try:
                info = await validate_port(port, baud_rate)
            except ConsoleError as err:
                _LOGGER.debug("Cannot connect to %s: %s", port, err)
                errors["base"] = "cannot_connect"
            except ParseError as err:
                _LOGGER.debug("Unexpected info output on %s: %s", port, err)
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(info.barcode or port)
                self._abort_if_unique_id_configured(updates={CONF_SERIAL_PORT: port})
                title = f"Pylontech {info.device_name or 'battery'}"
                return self.async_create_entry(
                    title=title,
                    data={CONF_SERIAL_PORT: port, CONF_BAUD_RATE: baud_rate},
                )

        ports = await self.hass.async_add_executor_job(_list_ports)
        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERIAL_PORT, default=defaults.get(CONF_SERIAL_PORT, vol.UNDEFINED)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=ports, custom_value=True, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(
                    CONF_BAUD_RATE, default=str(defaults.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE))
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[str(b) for b in BAUD_RATES], mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PylontechOptionsFlow()


class PylontechOptionsFlow(OptionsFlow):
    """Handle options for Pylontech US."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={key: int(value) for key, value in user_input.items()}
            )

        options = self.config_entry.options

        def number(minimum: int, maximum: int, unit: str | None = None) -> NumberSelector:
            config = NumberSelectorConfig(
                min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
            )
            if unit:
                config["unit_of_measurement"] = unit
            return NumberSelector(config)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): number(5, 3600, "s"),
                vol.Required(
                    CONF_CELL_POLL_EVERY,
                    default=options.get(CONF_CELL_POLL_EVERY, DEFAULT_CELL_POLL_EVERY),
                ): number(0, 1000),
                vol.Required(
                    CONF_STAT_POLL_EVERY,
                    default=options.get(CONF_STAT_POLL_EVERY, DEFAULT_STAT_POLL_EVERY),
                ): number(0, 1000),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
