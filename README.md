# Pylontech US (console) for Home Assistant

Local polling integration for Pylontech US-series batteries (US2000C, US3000C, US5000, ...) through the RS232 **console** port of the master module.

## Features

- One config entry per console port (stack). Linked modules behind the master appear as separate devices. The master console only answers `info` and `stat` for itself, so serial number, firmware, cycle count and state of health are only available for the master module.
- Stack sensors: voltage, total current and power, average state of charge, lowest/highest cell voltage and temperature, module count, BMS clock.
- Module sensors: voltage, current, power, state of charge, temperatures, lowest/highest cell voltage and delta, state (charging/discharging/idle/error), cycle count and state of health (master only).
- Per-cell voltage and temperature sensors (disabled by default).
- Alarm binary sensor per module (on when any status field is not `Normal`, or the module reports `SysError`).
- Button to sync the BMS clock with Home Assistant.
- Diagnostics include the raw console output.

## Hardware

Use a Pylontech console cable (RJ45 for US2000C/US3000/US5000, RJ11 on older US2000) and any USB-RS232 adapter. The console runs at 115200 8N1. Older US2000 units that need the 1200-baud wake-up sequence are not supported.

## Installation

### HACS

1. HACS, Integrations, three dots, Custom repositories, add this repository as an *Integration*.
2. Install **Pylontech US (console)** and restart Home Assistant.

### Manual

Copy `custom_components/pylontech_us` into your `config/custom_components` folder and restart.

## Configuration

Settings, Devices & services, Add integration, **Pylontech US (console)**. Pick the serial port (preferably the `/dev/serial/by-id/...` path) and the baud rate.

Options:

- **Polling interval** (default 30 s): how often `pwr` is read.
- **Read cell data every N polls** (default 4): `bat` per module.
- **Read statistics and BMS clock every N polls** (default 20): `stat` per module and `time`.

## Energy dashboard

The integration does not keep energy counters. Create two *Integral* helpers (Riemann sum, left method) on a template sensor that splits the stack power into charge (positive) and discharge (negative) parts, then use them in the Energy dashboard as battery in/out.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check .
.venv/bin/pytest
```
