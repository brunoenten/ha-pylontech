"""Tests for setting up the integration with a mocked console."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pylontech_us.const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DOMAIN

UNIQUE_ID = "PPTBH02400710243"


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


async def test_setup_creates_devices_and_entities(hass: HomeAssistant, mock_console) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    devices = {
        identifier: device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        for _, identifier in device.identifiers
    }
    assert set(devices) == {UNIQUE_ID, f"{UNIQUE_ID}_1", f"{UNIQUE_ID}_2"}
    module = devices[f"{UNIQUE_ID}_1"]
    assert module.via_device_id == devices[UNIQUE_ID].id
    assert module.serial_number == "PPTBH02400710243"

    entities = er.async_get(hass)
    soc_id = entities.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_soc")
    assert hass.states.get(soc_id).state == "66.5"
    module_soc = entities.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_1_soc")
    assert hass.states.get(module_soc).state == "67"
    state_id = entities.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_1_state")
    assert hass.states.get(state_id).state == "discharging"
    cycles_id = entities.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_1_cycles")
    assert hass.states.get(cycles_id).state == "430"
    alarm_id = entities.async_get_entity_id("binary_sensor", DOMAIN, f"{UNIQUE_ID}_1_alarm")
    assert hass.states.get(alarm_id).state == "off"

    cell_id = entities.async_get_entity_id("sensor", DOMAIN, f"{UNIQUE_ID}_1_cell_voltage_3")
    assert cell_id is not None
    assert entities.async_get(cell_id).disabled_by is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_sync_time_button(hass: HomeAssistant, mock_console) -> None:
    await _setup(hass)
    entity_id = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{UNIQUE_ID}_sync_time")
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    sent = [call.args[0] for call in mock_console.call_args_list]
    assert any(cmd.startswith("time ") and len(cmd.split()) == 7 for cmd in sent)
