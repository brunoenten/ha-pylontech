"""Diagnostics for the Pylontech US console integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PylontechConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PylontechConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "master": asdict(coordinator.master) if coordinator.master else None,
        "data": asdict(coordinator.data) if coordinator.data else None,
        "raw": coordinator.raw,
    }
