"""The Pylontech US console integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import PylontechConfigEntry, PylontechCoordinator
from .entity import stack_device_info

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PylontechConfigEntry) -> bool:
    """Set up Pylontech US from a config entry."""
    coordinator = PylontechCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await coordinator.console.close()
        raise
    stack_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **stack_device_info(coordinator)
    )
    coordinator.stack_device_id = stack_device.id
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PylontechConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.console.close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: PylontechConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
