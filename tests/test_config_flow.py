"""Tests for the config and options flows."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pylontech_us.console import ConsoleError
from custom_components.pylontech_us.const import (
    CONF_BAUD_RATE,
    CONF_CELL_POLL_EVERY,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_STAT_POLL_EVERY,
    DOMAIN,
)

PORT = "/dev/serial/by-id/usb-FTDI-port0"


async def test_user_flow(hass: HomeAssistant, mock_console) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    with patch("custom_components.pylontech_us.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: PORT, CONF_BAUD_RATE: "115200"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pylontech US2000C"
    assert result["data"] == {CONF_SERIAL_PORT: PORT, CONF_BAUD_RATE: 115200}
    assert result["result"].unique_id == "PPTCR03100C22779"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.pylontech_us.console.PylontechConsole.command",
        side_effect=ConsoleError("no prompt"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: PORT, CONF_BAUD_RATE: "115200"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_response(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.pylontech_us.console.PylontechConsole.command",
        return_value="garbage\r\npylon>",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: PORT, CONF_BAUD_RATE: "115200"}
        )
    assert result["errors"] == {"base": "invalid_response"}


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_SERIAL_PORT: PORT, CONF_BAUD_RATE: 115200})
    entry.add_to_hass(hass)
    with patch("custom_components.pylontech_us.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_SCAN_INTERVAL: 15, CONF_CELL_POLL_EVERY: 2, CONF_STAT_POLL_EVERY: 10},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SCAN_INTERVAL: 15,
        CONF_CELL_POLL_EVERY: 2,
        CONF_STAT_POLL_EVERY: 10,
    }
