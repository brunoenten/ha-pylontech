"""Buttons for the Pylontech US console integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .coordinator import PylontechConfigEntry
from .entity import PylontechStackEntity

SYNC_TIME = ButtonEntityDescription(
    key="sync_time",
    translation_key="sync_time",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PylontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SyncTimeButton(entry.runtime_data, SYNC_TIME)])


class SyncTimeButton(PylontechStackEntity, ButtonEntity):
    """Set the BMS clock to Home Assistant's time."""

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_sync_time()
        except UpdateFailed as err:
            raise HomeAssistantError(str(err)) from err
