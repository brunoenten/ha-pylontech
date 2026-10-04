"""Parsers for Pylontech US console command output."""

from __future__ import annotations

import re
from datetime import datetime

from .models import CellData, ModuleInfo, PowerRow, StatData

_DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
_INT_RE = re.compile(r"^-?\d+$")
_NUM_UNIT_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*([A-Za-z%]*)$")
_NOISE = ("@", "$$", "Command completed", "Press [Enter]")


class ParseError(ValueError):
    """Raised when console output cannot be parsed."""


def clean_lines(raw: str) -> list[str]:
    """Return meaningful lines of a response, without echo, prompt and markers."""
    lines = []
    for line in raw.replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(_NOISE) or re.match(r"^pylon\w*>", stripped):
            continue
        lines.append(line.rstrip())
    return lines


def _milli(value: str) -> float | None:
    if not _INT_RE.match(value):
        return None
    return int(value) / 1000


def _percent(value: str) -> int | None:
    value = value.rstrip("%")
    return int(value) if _INT_RE.match(value) else None


def _text(value: str | None) -> str | None:
    if value is None or value in ("-", ""):
        return None
    return value


def _merge_datetime_tokens(tokens: list[str]) -> list[str]:
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and _DATE_RE.match(tokens[i]) and _TIME_RE.match(tokens[i + 1]):
            merged.append(f"{tokens[i]} {tokens[i + 1]}")
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    return merged


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    match = _DATETIME_RE.search(value)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_pwr(raw: str) -> dict[int, PowerRow]:
    """Parse `pwr` output into rows keyed by module address, skipping absent modules."""
    lines = clean_lines(raw)
    header: list[str] | None = None
    rows: dict[int, PowerRow] = {}
    for line in lines:
        tokens = line.split()
        if tokens and tokens[0] == "Power" and "Volt" in tokens:
            header = tokens
            continue
        if header is None or not tokens or not _INT_RE.match(tokens[0]):
            continue
        if "Absent" in tokens:
            continue
        values = dict(zip(header, _merge_datetime_tokens(tokens), strict=False))
        voltage = _milli(values.get("Volt", ""))
        current = _milli(values.get("Curr", ""))
        temperature = _milli(values.get("Tempr", ""))
        if voltage is None or current is None or temperature is None:
            continue
        address = int(tokens[0])
        rows[address] = PowerRow(
            address=address,
            voltage=voltage,
            current=current,
            temperature=temperature,
            temperature_low=_milli(values.get("Tlow", "")),
            temperature_high=_milli(values.get("Thigh", "")),
            cell_voltage_low=_milli(values.get("Vlow", "")),
            cell_voltage_high=_milli(values.get("Vhigh", "")),
            base_state=_text(values.get("Base.St")),
            volt_state=_text(values.get("Volt.St")),
            curr_state=_text(values.get("Curr.St")),
            temp_state=_text(values.get("Temp.St")),
            soc=_percent(values.get("Coulomb", "")),
            time=_parse_datetime(values.get("Time")),
            bv_state=_text(values.get("B.V.St")),
            bt_state=_text(values.get("B.T.St")),
            mos_temperature=_milli(values.get("MosTempr", "")),
            mt_state=_text(values.get("M.T.St")),
            raw=values,
        )
    if header is None:
        raise ParseError("No 'pwr' header found")
    return rows


def _key_values(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in clean_lines(raw):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = re.sub(r"\s+", " ", key.strip()).lower()
        if key:
            result[key] = value.strip()
    return result


def _current_ma(value: str | None) -> float | None:
    if not value:
        return None
    match = _NUM_UNIT_RE.match(value.replace(" ", ""))
    if not match:
        return None
    number = float(match.group(1))
    return number / 1000 if match.group(2).lower() == "ma" else number


def parse_info(raw: str) -> ModuleInfo:
    """Parse `info` output."""
    kv = _key_values(raw)
    if "barcode" not in kv and "device name" not in kv and "manufacturer" not in kv:
        raise ParseError("No 'info' fields found")
    address = kv.get("device address")
    cells = kv.get("cell number")
    return ModuleInfo(
        address=int(address) if address and address.isdigit() else None,
        manufacturer=kv.get("manufacturer"),
        device_name=kv.get("device name"),
        board_version=kv.get("board version"),
        main_soft_version=kv.get("main soft version"),
        soft_version=kv.get("soft version"),
        boot_version=kv.get("boot version"),
        comm_version=kv.get("comm version"),
        release_date=kv.get("release date"),
        barcode=kv.get("barcode") or None,
        specification=kv.get("specification"),
        cell_count=int(cells) if cells and cells.isdigit() else None,
        max_discharge_current=_current_ma(kv.get("max dischg curr")),
        max_charge_current=_current_ma(kv.get("max charge curr")),
        raw=kv,
    )


def parse_bat(raw: str) -> list[CellData]:
    """Parse `bat` output into per-cell data."""
    cells: list[CellData] = []
    for line in clean_lines(raw):
        tokens = line.split()
        if len(tokens) < 4 or not all(_INT_RE.match(t) for t in tokens[:4]):
            continue
        rest = tokens[4:]
        states = [t for t in rest if not _INT_RE.match(t) and not t.endswith("%")]
        states = [t for t in states if t.lower() not in ("mah", "y", "n")]
        soc = next((_percent(t) for t in rest if t.endswith("%")), None)
        coulomb = None
        for i, token in enumerate(rest):
            if token.lower() == "mah" and i > 0 and _INT_RE.match(rest[i - 1]):
                coulomb = int(rest[i - 1]) / 1000
            elif token.lower().endswith("mah") and _INT_RE.match(token[:-3]):
                coulomb = int(token[:-3]) / 1000
        balancing = None
        if rest and rest[-1] in ("Y", "N"):
            balancing = rest[-1] == "Y"
        cells.append(
            CellData(
                index=int(tokens[0]),
                voltage=int(tokens[1]) / 1000,
                current=int(tokens[2]) / 1000,
                temperature=int(tokens[3]) / 1000,
                base_state=states[0] if len(states) > 0 else None,
                volt_state=states[1] if len(states) > 1 else None,
                curr_state=states[2] if len(states) > 2 else None,
                temp_state=states[3] if len(states) > 3 else None,
                soc=soc,
                coulomb=coulomb,
                balancing=balancing,
            )
        )
    if not cells:
        raise ParseError("No cell rows found in 'bat' output")
    return cells


def parse_stat(raw: str) -> StatData:
    """Parse `stat` output."""
    kv = _key_values(raw)
    cycles = kv.get("cycle times")
    soh = kv.get("soh")
    return StatData(
        cycles=int(cycles) if cycles and cycles.isdigit() else None,
        soh=int(soh) if soh and soh.isdigit() else None,
        raw=kv,
    )


def parse_time(raw: str) -> datetime | None:
    """Parse `time` output."""
    return _parse_datetime(raw)


def format_time_command(value: datetime) -> str:
    """Return the console command that sets the BMS clock."""
    return value.strftime("time %y %m %d %H %M %S")
