"""Tests for setting up the integration with a mocked console."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pylontech_us.const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DOMAIN

UNIQUE_ID = "PPTCR03100C22779"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        title="Pylontech US2000C",
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_BAUD_RATE: 115200},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _devices(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, dr.DeviceEntry]:
    return {
        identifier: device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        for _, identifier in device.identifiers
    }


def _state(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None, unique_id
    return hass.states.get(entity_id).state


async def test_setup_single_module(hass: HomeAssistant, mock_console) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    devices = _devices(hass, entry)
    assert set(devices) == {UNIQUE_ID, f"{UNIQUE_ID}_1"}
    module = devices[f"{UNIQUE_ID}_1"]
    assert module.via_device_id == devices[UNIQUE_ID].id
    assert module.serial_number == UNIQUE_ID
    assert module.model == "US2000C"

    assert _state(hass, "sensor", f"{UNIQUE_ID}_soc") == "14.0"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_1_soc") == "14"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_1_voltage") == "50.231"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_1_state") == "charging"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_1_cycles") == "1157"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_1_soh") == "88"
    assert _state(hass, "binary_sensor", f"{UNIQUE_ID}_1_alarm") == "off"

    cell_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{UNIQUE_ID}_1_cell_voltage_14"
    )
    assert er.async_get(hass).async_get(cell_id).disabled_by is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("pwr_fixture", ["pwr_stack.txt"])
async def test_setup_stack(hass: HomeAssistant, mock_console) -> None:
    entry = await _setup(hass)
    addresses = [1, 2, 3, 5, 6, 7, 8]
    devices = _devices(hass, entry)
    assert set(devices) == {UNIQUE_ID, *(f"{UNIQUE_ID}_{a}" for a in addresses)}
    assert devices[f"{UNIQUE_ID}_3"].serial_number is None
    assert devices[f"{UNIQUE_ID}_3"].name == "Pylontech module 3"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_module_count") == "7"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_1_state") == "error"
    assert _state(hass, "binary_sensor", f"{UNIQUE_ID}_1_alarm") == "on"
    assert _state(hass, "binary_sensor", f"{UNIQUE_ID}_2_alarm") == "off"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_5_state") == "discharging"
    assert _state(hass, "sensor", f"{UNIQUE_ID}_3_soc") == "73"

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_1_soh")
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_3_soh") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_3_cell_voltage_0")

    sent = [call.args[0] for call in mock_console.call_args_list]
    assert "bat 3" in sent
    assert not any(cmd.startswith(("info ", "stat ")) for cmd in sent)


async def test_sync_time_button(hass: HomeAssistant, mock_console) -> None:
    await _setup(hass)
    entity_id = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{UNIQUE_ID}_sync_time")
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    sent = [call.args[0] for call in mock_console.call_args_list]
    assert any(cmd.startswith("time ") and len(cmd.split()) == 7 for cmd in sent)
