"""Tests for console output parsers."""

from datetime import datetime

import pytest

from custom_components.pylontech_us.parser import (
    ParseError,
    format_time_command,
    parse_bat,
    parse_info,
    parse_pwr,
    parse_stat,
    parse_time,
)

from .conftest import load_fixture


def test_parse_pwr() -> None:
    rows = parse_pwr(load_fixture("pwr_sample.txt"))
    assert list(rows) == [1, 2]
    row = rows[1]
    assert row.voltage == 49.735
    assert row.current == -1.25
    assert row.temperature == 21.0
    assert row.temperature_low == 20.0
    assert row.cell_voltage_low == 3.313
    assert row.cell_voltage_high == 3.318
    assert row.base_state == "Dischg"
    assert row.soc == 67
    assert row.time == datetime(2026, 10, 4, 15, 0, 0)
    assert row.bv_state == "Normal"
    assert row.mos_temperature == 22.0
    assert row.alarms == {}
    assert row.power == round(49.735 * -1.25, 1)


def test_parse_pwr_alarm() -> None:
    raw = load_fixture("pwr_sample.txt").replace(
        "Dischg   Normal   Normal   Normal   67%", "Dischg   Normal   Normal   HighT    67%", 1
    )
    assert parse_pwr(raw)[1].alarms == {"temp_state": "HighT"}


def test_parse_pwr_without_header() -> None:
    with pytest.raises(ParseError):
        parse_pwr("pwr\r\n$$\r\npylon>")


def test_parse_pwr_legacy_columns() -> None:
    raw = (
        "pwr\r\n@\r\n"
        "Power Volt   Curr   Tempr  Tlow   Thigh  Vlow   Vhigh  Base.St  Volt.St  Curr.St  "
        "Temp.St  Coulomb  Time                 B.V.St   B.T.St  \r\n"
        "1     51000  2000   25000  24000  25000  3400   3402   Charge   Normal   Normal   "
        "Normal   95%      2019-01-01 00:00:00  Normal   Normal  \r\n"
        "Command completed successfully\r\n$$\r\n\rpylon>"
    )
    row = parse_pwr(raw)[1]
    assert row.base_state == "Charge"
    assert row.soc == 95
    assert row.mos_temperature is None


def test_parse_info() -> None:
    info = parse_info(load_fixture("info_sample.txt"))
    assert info.address == 1
    assert info.device_name == "US2000C"
    assert info.barcode == "PPTBH02400710243"
    assert info.cell_count == 15
    assert info.main_soft_version == "B66.6"
    assert info.soft_version == "V2.4"
    assert info.firmware == "B66.6 / V2.4"
    assert info.max_discharge_current == -100.0
    assert info.max_charge_current == 102.0


def test_parse_info_invalid() -> None:
    with pytest.raises(ParseError):
        parse_info("info 5\r\nInvalid command\r\n$$\r\npylon>")


def test_parse_bat() -> None:
    cells = parse_bat(load_fixture("bat_sample.txt"))
    assert len(cells) == 15
    cell = cells[3]
    assert cell.index == 3
    assert cell.voltage == 3.318
    assert cell.current == -1.25
    assert cell.temperature == 20.0
    assert cell.base_state == "Dischg"
    assert cell.volt_state == "Normal"
    assert cell.soc == 67
    assert cell.coulomb == 33.562
    assert cell.balancing is True
    assert cells[0].balancing is False


def test_parse_stat() -> None:
    assert parse_stat(load_fixture("stat_sample.txt")).cycles == 430


def test_parse_time() -> None:
    assert parse_time(load_fixture("time_sample.txt")) == datetime(2026, 10, 4, 15, 0, 0)


def test_format_time_command() -> None:
    assert format_time_command(datetime(2026, 1, 2, 3, 4, 5)) == "time 26 01 02 03 04 05"
