"""Relay output for a small buzzer only; no firing-device support."""
from __future__ import annotations

import os
import threading
import time


class Buzzer:
    def __init__(self, pin: int, active_low: bool, enabled: bool, simulation: bool):
        self.enabled = enabled
        self.simulation = simulation
        self._last_pulse = 0.0
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._output = None
        if enabled and not simulation:
            os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
            from gpiozero import OutputDevice
            self._output = OutputDevice(pin, active_high=not active_low, initial_value=False)

    def off(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if self._output:
                self._output.off()

    def pulse(self, duration_ms: int, cooldown_s: float) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            now = time.monotonic()
            if now - self._last_pulse < cooldown_s:
                return False
            self._last_pulse = now
            if self._output:
                self._output.on()
                self._timer = threading.Timer(duration_ms / 1000, self.off)
                self._timer.daemon = True
                self._timer.start()
            return True

    def close(self) -> None:
        self.off()
        if self._output:
            self._output.close()
