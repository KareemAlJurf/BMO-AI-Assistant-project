#!/usr/bin/env python3
"""
battery_manager.py

Low-level battery reader for the Geekworm X1203 UPS used in the BMO build.

The X1203 exposes a MAX17040/MAX17040G+-compatible fuel gauge on I2C bus 1
at address 0x36.

This module intentionally does NOT control the BMO UI. It only:
- reads battery voltage
- reads state-of-charge percentage
- classifies the battery level
- optionally prints/streams status for debugging

Keeping hardware access separate makes it easier to reuse and test.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime

try:
    from smbus2 import SMBus
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: smbus2\n"
        "Install it inside the BMO venv with:\n"
        "  source ~/be-more-agent/venv/bin/activate\n"
        "  pip install smbus2"
    ) from exc


I2C_BUS = 1
I2C_ADDRESS = 0x36

VCELL_REGISTER = 0x02
SOC_REGISTER = 0x04

LOW_BATTERY_PERCENT = 20.0
CRITICAL_BATTERY_PERCENT = 15.0
SHUTDOWN_BATTERY_PERCENT = 5.0


@dataclass(frozen=True)
class BatteryStatus:
    percent: float
    voltage: float
    level: str
    timestamp: str


class X1203BatteryManager:
    """Read battery information from the X1203 fuel gauge."""

    def __init__(self, bus: int = I2C_BUS, address: int = I2C_ADDRESS):
        self.bus_number = bus
        self.address = address

    def _read_two_bytes(self, register: int) -> tuple[int, int]:
        with SMBus(self.bus_number) as bus:
            values = bus.read_i2c_block_data(self.address, register, 2)

        if len(values) != 2:
            raise RuntimeError(
                f"Expected 2 bytes from register 0x{register:02X}, got {values!r}"
            )

        return values[0], values[1]

    def read_voltage(self) -> float:
        """
        Read battery voltage.

        MAX17040 VCELL is a 12-bit value with 1.25 mV per LSB.
        """
        msb, lsb = self._read_two_bytes(VCELL_REGISTER)
        raw = (msb << 4) | (lsb >> 4)
        return raw * 0.00125

    def read_percent(self) -> float:
        """
        Read state of charge.

        SOC MSB is the integer percent and the LSB is 1/256 percent.
        """
        msb, lsb = self._read_two_bytes(SOC_REGISTER)
        percent = msb + (lsb / 256.0)
        return max(0.0, min(percent, 100.0))

    @staticmethod
    def classify(percent: float) -> str:
        if percent <= SHUTDOWN_BATTERY_PERCENT:
            return "shutdown"
        if percent <= CRITICAL_BATTERY_PERCENT:
            return "critical"
        if percent <= LOW_BATTERY_PERCENT:
            return "low"
        return "normal"

    def read_status(self) -> BatteryStatus:
        percent = self.read_percent()
        voltage = self.read_voltage()

        return BatteryStatus(
            percent=round(percent, 2),
            voltage=round(voltage, 3),
            level=self.classify(percent),
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Geekworm X1203 battery status")
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="continuously print battery status",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="monitor interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print status as JSON",
    )
    args = parser.parse_args()

    manager = X1203BatteryManager()

    while True:
        try:
            status = manager.read_status()
        except Exception as exc:
            print(f"[BATTERY] Read failed: {exc}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(asdict(status)))
        else:
            print(
                f"[BATTERY] {status.percent:.2f}% | "
                f"{status.voltage:.3f} V | {status.level}"
            )

        if not args.monitor:
            return 0

        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
