"""Base entities for the Pylontech US console integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PylontechCoordinator
from .models import ModuleData


def stack_id(coordinator: PylontechCoordinator) -> str:
    entry = coordinator.config_entry
    return entry.unique_id or entry.entry_id


def stack_device_info(coordinator: PylontechCoordinator) -> DeviceInfo:
    master = coordinator.master
    return DeviceInfo(
        identifiers={(DOMAIN, stack_id(coordinator))},
        name=coordinator.config_entry.title,
        manufacturer="Pylontech",
        model="US stack",
        sw_version=master.firmware if master else None,
    )


def module_device_info(coordinator: PylontechCoordinator, address: int) -> DeviceInfo:
    module = coordinator.data.modules.get(address) if coordinator.data else None
    info = module.info if module else None
    return DeviceInfo(
        identifiers={(DOMAIN, f"{stack_id(coordinator)}_{address}")},
        name=f"{info.device_name if info and info.device_name else 'Pylontech'} #{address}",
        manufacturer="Pylontech",
        model=info.device_name if info else None,
        serial_number=info.barcode if info else None,
        sw_version=info.firmware if info else None,
        hw_version=info.board_version if info else None,
        via_device=(DOMAIN, stack_id(coordinator)),
    )


class PylontechStackEntity(CoordinatorEntity[PylontechCoordinator]):
    """Entity attached to the stack device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PylontechCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{stack_id(coordinator)}_{description.key}"
        self._attr_device_info = stack_device_info(coordinator)


class PylontechModuleEntity(CoordinatorEntity[PylontechCoordinator]):
    """Entity attached to one module device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PylontechCoordinator,
        description: EntityDescription,
        address: int,
        key_suffix: str = "",
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.address = address
        self._attr_unique_id = f"{stack_id(coordinator)}_{address}_{description.key}{key_suffix}"
        self._attr_device_info = module_device_info(coordinator, address)

    @property
    def module(self) -> ModuleData | None:
        return self.coordinator.data.modules.get(self.address) if self.coordinator.data else None

    @property
    def available(self) -> bool:
        return super().available and self.module is not None
