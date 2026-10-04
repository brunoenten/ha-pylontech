"""Tests for console output parsers, using output captured from a US2000C."""

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
    rows = parse_pwr(load_fixture("pwr.txt"))
    assert list(rows) == [1]
    row = rows[1]
    assert row.voltage == 50.231
    assert row.current == 1.784
    assert row.temperature == 33.7
    assert row.temperature_low == 28.2
    assert row.temperature_high == 28.9
    assert row.cell_voltage_low == 3.348
    assert row.cell_voltage_high == 3.349
    assert row.base_state == "Charge"
    assert row.soc == 14
    assert row.time == datetime(2026, 10, 4, 20, 32, 13)
    assert row.bv_state == "Normal"
    assert row.mos_temperature == 31.7
    assert row.mt_state == "Normal"
    assert row.alarms == {}
    assert row.power == round(50.231 * 1.784, 1)


def test_parse_pwr_stack() -> None:
    rows = parse_pwr(load_fixture("pwr_stack.txt"))
    assert list(rows) == [1, 2, 3, 5, 6, 7, 8]
    assert rows[1].base_state == "SysError"
    assert rows[1].alarms == {"base_state": "SysError"}
    assert rows[5].current == -2.824
    assert rows[8].base_state == "Charge"
    assert rows[2].mos_temperature is None
    assert rows[2].mt_state is None
    assert rows[2].alarms == {}


def test_parse_bat_slave() -> None:
    cells = parse_bat(load_fixture("bat_slave.txt"))
    assert len(cells) == 15
    assert cells[0].soc == 73
    assert cells[0].coulomb == 32.911


def test_parse_pwr_alarm() -> None:
    raw = load_fixture("pwr.txt").replace(
        "Charge   Normal   Normal   Normal   14%", "Charge   Normal   Normal   HighT    14%", 1
    )
    assert parse_pwr(raw)[1].alarms == {"temp_state": "HighT"}


def test_parse_pwr_without_header() -> None:
    with pytest.raises(ParseError):
        parse_pwr(load_fixture("pwr_single.txt"))


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


@pytest.mark.parametrize("fixture", ["info.txt", "info_master.txt"])
def test_parse_info(fixture: str) -> None:
    info = parse_info(load_fixture(fixture))
    assert info.address == 1
    assert info.device_name == "US2000C"
    assert info.barcode == "PPTCR03100C22779"
    assert info.board_version == "V10R04"
    assert info.cell_count == 15
    assert info.firmware == "B67.5.0 / V1.7"
    assert info.max_discharge_current == -90.0
    assert info.max_charge_current == 90.0


def test_parse_info_invalid() -> None:
    with pytest.raises(ParseError):
        parse_info("info 5\r\nInvalid command\r\n$$\r\npylon>")


def test_parse_bat() -> None:
    cells = parse_bat(load_fixture("bat.txt"))
    assert len(cells) == 15
    cell = cells[5]
    assert cell.index == 5
    assert cell.voltage == 3.35
    assert cell.current == 1.784
    assert cell.temperature == 28.2
    assert cell.base_state == "Charge"
    assert cell.volt_state == "Normal"
    assert cell.temp_state == "Normal"
    assert cell.soc == 14
    assert cell.coulomb == 6.313
    assert cell.balancing is False


def test_parse_stat() -> None:
    stat = parse_stat(load_fixture("stat.txt"))
    assert stat.cycles == 1157
    assert stat.soh == 88


def test_parse_time() -> None:
    assert parse_time(load_fixture("time.txt")) == datetime(2026, 10, 4, 20, 32, 39)


def test_format_time_command() -> None:
    assert format_time_command(datetime(2026, 1, 2, 3, 4, 5)) == "time 26 01 02 03 04 05"
