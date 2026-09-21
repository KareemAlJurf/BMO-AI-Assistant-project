#!/usr/bin/env python3
"""
battery_integration.py

BMO-facing battery behavior for the Geekworm X1203.

Behavior:
- <= 20%: request the existing BMO low-battery face
- <= 15%: speak one low-battery warning
- <= 5%: after 3 consecutive readings, request a safe shutdown

This file is deliberately separate from agent_hailo.py so the battery feature
is easy to maintain, test, and publish without replacing the upstream agent.

The integration uses callbacks supplied by agent_hailo.py:
- set_low_battery_face(percent, message)
- speak(message)
- shutdown()

Nothing here imports Tkinter or BotStates directly.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from battery_manager import X1203BatteryManager


log = logging.getLogger(__name__)


@dataclass
class BatteryPolicy:
    low_percent: float = 20.0
    spoken_warning_percent: float = 15.0
    shutdown_percent: float = 5.0
    shutdown_confirm_readings: int = 3
    check_interval_seconds: float = 30.0
    warning_reset_percent: float = 25.0


class BMOBatteryIntegration:
    """
    Background battery monitor that triggers BMO callbacks.

    Parameters
    ----------
    stop_event:
        Existing threading.Event used by the BMO agent to stop background work.
    set_low_battery_face:
        callback(percent, message)
    speak:
        callback(message)
    shutdown:
        callback() that performs the actual system shutdown
    is_busy:
        optional callback returning True while BMO is busy
    """

    def __init__(
        self,
        stop_event: threading.Event,
        set_low_battery_face: Callable[[float, str], None],
        speak: Callable[[str], None],
        shutdown: Callable[[], None],
        is_busy: Optional[Callable[[], bool]] = None,
        policy: Optional[BatteryPolicy] = None,
        manager: Optional[X1203BatteryManager] = None,
    ):
        self.stop_event = stop_event
        self.set_low_battery_face = set_low_battery_face
        self.speak = speak
        self.shutdown = shutdown
        self.is_busy = is_busy or (lambda: False)
        self.policy = policy or BatteryPolicy()
        self.manager = manager or X1203BatteryManager()

        self.last_percent: Optional[float] = None
        self.last_voltage: Optional[float] = None

        self._warning_spoken = False
        self._shutdown_count = 0
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="bmo-battery-monitor",
            daemon=True,
        )
        self._thread.start()

    def _monitor_loop(self) -> None:
        log.info("[BATTERY] X1203 monitor started")

        while not self.stop_event.is_set():
            try:
                status = self.manager.read_status()
                self.last_percent = status.percent
                self.last_voltage = status.voltage

                print(
                    f"[BATTERY] {status.percent:.1f}% | "
                    f"{status.voltage:.3f} V | {status.level}"
                )

                self._apply_policy(status.percent)

            except Exception as exc:
                log.exception("[BATTERY] Monitor error: %s", exc)

            self.stop_event.wait(self.policy.check_interval_seconds)

    def _apply_policy(self, percent: float) -> None:
        # Restore the one-time spoken warning after the battery has been charged.
        if percent >= self.policy.warning_reset_percent:
            self._warning_spoken = False

        # 20%: show the project's existing low-battery face.
        if percent <= self.policy.low_percent and not self.is_busy():
            try:
                self.set_low_battery_face(percent, f"Battery {percent:.0f}%")
            except Exception:
                log.exception("[BATTERY] Failed to set low-battery face")

        # 15%: warn once per discharge cycle.
        if (
            percent <= self.policy.spoken_warning_percent
            and not self._warning_spoken
        ):
            self._warning_spoken = True
            try:
                self.set_low_battery_face(percent, "I'm getting tired...")
            except Exception:
                log.exception("[BATTERY] Failed to set warning face")

            try:
                self.speak("I'm getting tired. I need to be charged.")
            except Exception:
                log.exception("[BATTERY] Failed to speak low-battery warning")

        # 5%: require several consecutive readings before shutting down.
        if percent <= self.policy.shutdown_percent:
            self._shutdown_count += 1
            print(
                "[BATTERY] Critical reading "
                f"{self._shutdown_count}/{self.policy.shutdown_confirm_readings}"
            )
        else:
            self._shutdown_count = 0

        if self._shutdown_count >= self.policy.shutdown_confirm_readings:
            try:
                self.set_low_battery_face(
                    percent,
                    "Battery critical - shutting down",
                )
            except Exception:
                log.exception("[BATTERY] Failed to set shutdown face")

            try:
                self.speak("My battery is almost empty. Shutting down safely.")
            except Exception:
                log.exception("[BATTERY] Failed to speak shutdown warning")

            self.shutdown()
