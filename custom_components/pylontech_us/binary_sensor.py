"""Binary sensors for the Pylontech US console integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PylontechConfigEntry
from .entity import PylontechModuleEntity

ALARM = BinarySensorEntityDescription(
    key="alarm",
    translation_key="alarm",
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PylontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        if not coordinator.data:
            return
        new = [a for a in coordinator.data.modules if a not in known]
        known.update(new)
        if new:
            async_add_entities(AlarmBinarySensor(coordinator, ALARM, a) for a in new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class AlarmBinarySensor(PylontechModuleEntity, BinarySensorEntity):
    """On when any module status field is not Normal."""

    @property
    def is_on(self) -> bool | None:
        module = self.module
        return bool(module.power.alarms) if module else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        module = self.module
        if not module:
            return None
        row = module.power
        return {
            "volt_state": row.volt_state,
            "curr_state": row.curr_state,
            "temp_state": row.temp_state,
            "bv_state": row.bv_state,
            "bt_state": row.bt_state,
            "mt_state": row.mt_state,
        }
