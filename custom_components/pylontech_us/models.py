"""Data models for Pylontech US console data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

NORMAL = "Normal"


@dataclass
class ModuleInfo:
    """Static information from the `info` command."""

    address: int | None = None
    manufacturer: str | None = None
    device_name: str | None = None
    board_version: str | None = None
    main_soft_version: str | None = None
    soft_version: str | None = None
    boot_version: str | None = None
    comm_version: str | None = None
    release_date: str | None = None
    barcode: str | None = None
    specification: str | None = None
    cell_count: int | None = None
    max_discharge_current: float | None = None
    max_charge_current: float | None = None
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def firmware(self) -> str | None:
        """Return a human-readable firmware version string."""
        parts = [p for p in (self.main_soft_version, self.soft_version) if p]
        return " / ".join(parts) or None


@dataclass
class CellData:
    """Per-cell data from the `bat` command."""

    index: int
    voltage: float
    current: float
    temperature: float
    base_state: str | None = None
    volt_state: str | None = None
    curr_state: str | None = None
    temp_state: str | None = None
    soc: int | None = None
    coulomb: float | None = None
    balancing: bool | None = None


@dataclass
class PowerRow:
    """One module row from the `pwr` command."""

    address: int
    voltage: float
    current: float
    temperature: float
    temperature_low: float | None = None
    temperature_high: float | None = None
    cell_voltage_low: float | None = None
    cell_voltage_high: float | None = None
    base_state: str | None = None
    volt_state: str | None = None
    curr_state: str | None = None
    temp_state: str | None = None
    soc: int | None = None
    time: datetime | None = None
    bv_state: str | None = None
    bt_state: str | None = None
    mos_temperature: float | None = None
    mt_state: str | None = None
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def power(self) -> float:
        """Return power in W (positive when charging)."""
        return round(self.voltage * self.current, 1)

    @property
    def alarms(self) -> dict[str, str]:
        """Return status fields that are not Normal."""
        fields = {
            "volt_state": self.volt_state,
            "curr_state": self.curr_state,
            "temp_state": self.temp_state,
            "bv_state": self.bv_state,
            "bt_state": self.bt_state,
            "mt_state": self.mt_state,
        }
        return {k: v for k, v in fields.items() if v not in (None, NORMAL)}


@dataclass
class StatData:
    """Selected counters from the `stat` command."""

    cycles: int | None = None
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class ModuleData:
    """Everything known about one battery module."""

    address: int
    power: PowerRow
    info: ModuleInfo | None = None
    cells: list[CellData] = field(default_factory=list)
    stat: StatData | None = None


@dataclass
class StackData:
    """Data for a stack of modules behind one console."""

    master: ModuleInfo
    modules: dict[int, ModuleData] = field(default_factory=dict)
    bms_time: datetime | None = None

    def _rows(self) -> list[PowerRow]:
        return [m.power for m in self.modules.values()]

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def voltage(self) -> float | None:
        rows = self._rows()
        return round(sum(r.voltage for r in rows) / len(rows), 3) if rows else None

    @property
    def current(self) -> float | None:
        rows = self._rows()
        return round(sum(r.current for r in rows), 3) if rows else None

    @property
    def power(self) -> float | None:
        rows = self._rows()
        return round(sum(r.power for r in rows), 1) if rows else None

    @property
    def soc(self) -> float | None:
        socs = [r.soc for r in self._rows() if r.soc is not None]
        return round(sum(socs) / len(socs), 1) if socs else None

    @property
    def cell_voltage_low(self) -> float | None:
        vals = [r.cell_voltage_low for r in self._rows() if r.cell_voltage_low is not None]
        return min(vals) if vals else None

    @property
    def cell_voltage_high(self) -> float | None:
        vals = [r.cell_voltage_high for r in self._rows() if r.cell_voltage_high is not None]
        return max(vals) if vals else None

    @property
    def temperature_low(self) -> float | None:
        vals = [r.temperature_low for r in self._rows() if r.temperature_low is not None]
        return min(vals) if vals else None

    @property
    def temperature_high(self) -> float | None:
        vals = [r.temperature_high for r in self._rows() if r.temperature_high is not None]
        return max(vals) if vals else None
