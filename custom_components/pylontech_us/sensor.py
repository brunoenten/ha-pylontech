"""Sensors for the Pylontech US console integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import PylontechConfigEntry, PylontechCoordinator
from .entity import PylontechModuleEntity, PylontechStackEntity
from .models import CellData, ModuleData, StackData

STATE_MAP = {
    "Charge": "charging",
    "Dischg": "discharging",
    "Idle": "idle",
    "Balance": "balancing",
    "SysError": "error",
}
STATE_OPTIONS = [*STATE_MAP.values(), "other"]

type Value = float | int | str | datetime | None


@dataclass(frozen=True, kw_only=True)
class StackSensorDescription(SensorEntityDescription):
    value_fn: Callable[[StackData], Value]


@dataclass(frozen=True, kw_only=True)
class ModuleSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ModuleData], Value]
    exists_fn: Callable[[ModuleData], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class CellSensorDescription(SensorEntityDescription):
    value_fn: Callable[[CellData], Value]


def _voltage(key: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "key": key,
        "translation_key": key,
        "device_class": SensorDeviceClass.VOLTAGE,
        "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 3,
        **kwargs,
    }


def _temperature(key: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "key": key,
        "translation_key": key,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 1,
        **kwargs,
    }


CURRENT = {
    "device_class": SensorDeviceClass.CURRENT,
    "native_unit_of_measurement": UnitOfElectricCurrent.AMPERE,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 2,
}
POWER = {
    "device_class": SensorDeviceClass.POWER,
    "native_unit_of_measurement": UnitOfPower.WATT,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 0,
}
SOC = {
    "device_class": SensorDeviceClass.BATTERY,
    "native_unit_of_measurement": PERCENTAGE,
    "state_class": SensorStateClass.MEASUREMENT,
}


STACK_SENSORS: tuple[StackSensorDescription, ...] = (
    StackSensorDescription(**_voltage("voltage"), value_fn=lambda d: d.voltage),
    StackSensorDescription(key="current", translation_key="current", **CURRENT,
                           value_fn=lambda d: d.current),
    StackSensorDescription(key="power", translation_key="power", **POWER,
                           value_fn=lambda d: d.power),
    StackSensorDescription(key="soc", translation_key="soc", **SOC, value_fn=lambda d: d.soc),
    StackSensorDescription(**_voltage("cell_voltage_low"), value_fn=lambda d: d.cell_voltage_low),
    StackSensorDescription(**_voltage("cell_voltage_high"),
                           value_fn=lambda d: d.cell_voltage_high),
    StackSensorDescription(**_temperature("temperature_low"),
                           value_fn=lambda d: d.temperature_low),
    StackSensorDescription(**_temperature("temperature_high"),
                           value_fn=lambda d: d.temperature_high),
    StackSensorDescription(
        key="module_count",
        translation_key="module_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.module_count,
    ),
    StackSensorDescription(
        key="bms_time",
        translation_key="bms_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.bms_time.replace(tzinfo=dt_util.get_default_time_zone())
        if d.bms_time
        else None,
    ),
)

MODULE_SENSORS: tuple[ModuleSensorDescription, ...] = (
    ModuleSensorDescription(**_voltage("voltage"), value_fn=lambda m: m.power.voltage),
    ModuleSensorDescription(key="current", translation_key="current", **CURRENT,
                            value_fn=lambda m: m.power.current),
    ModuleSensorDescription(key="power", translation_key="power", **POWER,
                            value_fn=lambda m: m.power.power),
    ModuleSensorDescription(key="soc", translation_key="soc", **SOC,
                            value_fn=lambda m: m.power.soc),
    ModuleSensorDescription(**_temperature("temperature"), value_fn=lambda m: m.power.temperature),
    ModuleSensorDescription(**_temperature("temperature_low"),
                            value_fn=lambda m: m.power.temperature_low),
    ModuleSensorDescription(**_temperature("temperature_high"),
                            value_fn=lambda m: m.power.temperature_high),
    ModuleSensorDescription(
        **_temperature("mos_temperature", entity_registry_enabled_default=False),
        value_fn=lambda m: m.power.mos_temperature,
    ),
    ModuleSensorDescription(**_voltage("cell_voltage_low"),
                            value_fn=lambda m: m.power.cell_voltage_low),
    ModuleSensorDescription(**_voltage("cell_voltage_high"),
                            value_fn=lambda m: m.power.cell_voltage_high),
    ModuleSensorDescription(
        **_voltage(
            "cell_voltage_delta",
            suggested_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_display_precision=0,
        ),
        value_fn=lambda m: round(m.power.cell_voltage_high - m.power.cell_voltage_low, 3)
        if m.power.cell_voltage_high is not None and m.power.cell_voltage_low is not None
        else None,
    ),
    ModuleSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_OPTIONS,
        value_fn=lambda m: STATE_MAP.get(m.power.base_state or "", "other")
        if m.power.base_state
        else None,
    ),
    ModuleSensorDescription(
        key="cycles",
        translation_key="cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.stat.cycles if m.stat else None,
        exists_fn=lambda m: m.stat is not None,
    ),
    ModuleSensorDescription(
        key="soh",
        translation_key="soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.stat.soh if m.stat else None,
        exists_fn=lambda m: m.stat is not None,
    ),
)

CELL_SENSORS: tuple[CellSensorDescription, ...] = (
    CellSensorDescription(
        **_voltage("cell_voltage", entity_registry_enabled_default=False),
        value_fn=lambda c: c.voltage,
    ),
    CellSensorDescription(
        **_temperature("cell_temperature", entity_registry_enabled_default=False),
        value_fn=lambda c: c.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PylontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StackSensor(coordinator, d) for d in STACK_SENSORS)

    known_modules: set[int] = set()
    known_cells: set[tuple[int, int]] = set()

    @callback
    def _add_new() -> None:
        if not coordinator.data:
            return
        new: list[SensorEntity] = []
        for address, module in coordinator.data.modules.items():
            if address not in known_modules:
                known_modules.add(address)
                new.extend(
                    ModuleSensor(coordinator, d, address)
                    for d in MODULE_SENSORS
                    if d.exists_fn(module)
                )
            for cell in module.cells:
                if (address, cell.index) not in known_cells:
                    known_cells.add((address, cell.index))
                    new.extend(
                        CellSensor(coordinator, d, address, cell.index) for d in CELL_SENSORS
                    )
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class StackSensor(PylontechStackEntity, SensorEntity):
    entity_description: StackSensorDescription

    @property
    def native_value(self) -> Value:
        return self.entity_description.value_fn(self.coordinator.data)


class ModuleSensor(PylontechModuleEntity, SensorEntity):
    entity_description: ModuleSensorDescription

    @property
    def native_value(self) -> Value:
        module = self.module
        return self.entity_description.value_fn(module) if module else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "state" and self.module:
            return {"raw_state": self.module.power.base_state}
        return None


class CellSensor(PylontechModuleEntity, SensorEntity):
    entity_description: CellSensorDescription

    def __init__(
        self,
        coordinator: PylontechCoordinator,
        description: CellSensorDescription,
        address: int,
        index: int,
    ) -> None:
        super().__init__(coordinator, description, address, key_suffix=f"_{index}")
        self.index = index
        self._attr_translation_placeholders = {"cell": str(index + 1)}

    @property
    def _cell(self) -> CellData | None:
        module = self.module
        if not module:
            return None
        return next((c for c in module.cells if c.index == self.index), None)

    @property
    def available(self) -> bool:
        return super().available and self._cell is not None

    @property
    def native_value(self) -> Value:
        cell = self._cell
        return self.entity_description.value_fn(cell) if cell else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        cell = self._cell
        if not cell or self.entity_description.key != "cell_voltage":
            return None
        return {
            "balancing": cell.balancing,
            "volt_state": cell.volt_state,
            "temp_state": cell.temp_state,
        }
