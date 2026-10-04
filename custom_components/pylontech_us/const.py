"""Constants for the Pylontech US console integration."""

from typing import Final

DOMAIN: Final = "pylontech_us"

CONF_SERIAL_PORT: Final = "serial_port"
CONF_BAUD_RATE: Final = "baud_rate"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_CELL_POLL_EVERY: Final = "cell_poll_every"
CONF_STAT_POLL_EVERY: Final = "stat_poll_every"

DEFAULT_BAUD_RATE: Final = 115200
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_CELL_POLL_EVERY: Final = 4
DEFAULT_STAT_POLL_EVERY: Final = 20

BAUD_RATES: Final = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
