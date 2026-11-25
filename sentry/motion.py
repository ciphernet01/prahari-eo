"""Threaded step/dir control with per-axis soft limits and optional homing."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any


class Axis:
    def __init__(self, name: str, cfg: dict[str, Any], motor_cfg: dict,
                 home_pin: int | None = None):
        self.name = name
        self.cfg = cfg
        self.steps_per_degree = motor_cfg["steps_per_rev"] / 360.0
        self.min_steps = round(cfg["min_deg"] * self.steps_per_degree)
        self.max_steps = round(cfg["max_deg"] * self.steps_per_degree)
        self.max_sps = min(motor_cfg["max_steps_per_second"],
                           cfg["max_dps"] * self.steps_per_degree)
        self.accel = motor_cfg["acceleration_steps_per_second2"]
        self.position_steps = 0
        self.calibrated = False
        self._target_sps = 0.0
        self._actual_sps = 0.0
        self._homing = False
        self._lock = threading.RLock()
        self._closing = threading.Event()
        self._emergency = threading.Event()
        self._fault: str | None = None
        self._gpio = None
        self._home = None

        os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
        from gpiozero import DigitalInputDevice, OutputDevice
        self._gpio = (
            OutputDevice(cfg["dir"], initial_value=False),
            OutputDevice(cfg["step"], initial_value=False),
            OutputDevice(cfg["en"], initial_value=False),
        )
        if home_pin is not None:
            self._home = DigitalInputDevice(home_pin, pull_up=True, bounce_time=0.02)
        self._thread = threading.Thread(target=self._run, name=f"axis-{name}", daemon=True)
        self._thread.start()

    @property
    def pos_deg(self) -> float:
        with self._lock:
            return self.position_steps / self.steps_per_degree

    @property
    def fault(self) -> str | None:
        return self._fault

    @property
    def velocity_dps(self) -> float:
        with self._lock:
            return self._target_sps / self.steps_per_degree

    @property
    def stopped(self) -> bool:
        with self._lock:
            return abs(self._actual_sps) < 1.0

    def set_velocity_dps(self, dps: float) -> None:
        if not self.calibrated:
            raise RuntimeError(f"{self.name} axis has not been calibrated")
        sps = max(-self.max_sps, min(self.max_sps, dps * self.steps_per_degree))
        with self._lock:
            self._target_sps = sps
            if sps:
                self._emergency.clear()

    def stop(self) -> None:
        with self._lock:
            self._target_sps = 0.0

    def mark_zero(self) -> None:
        if not self.stopped:
            raise RuntimeError("Stop the axis before calibration")
        with self._lock:
            self.position_steps = 0
            self.calibrated = True
            self._fault = None

    def clear_fault(self) -> None:
        self._fault = None

    def home(self, timeout: float = 15.0) -> None:
        if self._home is None:
            raise RuntimeError(f"{self.name} home switch is not configured")
        self._homing = True
        try:
            if not self._home.is_active:
                self._set_raw_velocity(-self.max_sps * 0.12)
                until = time.monotonic() + timeout
                while not self._home.is_active and time.monotonic() < until:
                    time.sleep(0.01)
                self.stop()
                if not self._home.is_active:
                    raise RuntimeError("Homing timed out")
            self.stop()
            until = time.monotonic() + 2
            while not self.stopped and time.monotonic() < until:
                time.sleep(0.005)
            if not self.stopped:
                raise RuntimeError("Axis failed to stop at home switch")
            with self._lock:
                # The switch is installed at the configured negative travel end.
                self.position_steps = self.min_steps
                self.calibrated = True
            self._homing = False
            self._set_raw_velocity(self.max_sps * 0.12)
            until = time.monotonic() + timeout
            while self._home.is_active and time.monotonic() < until:
                time.sleep(0.01)
            self.stop()
            if self._home.is_active:
                raise RuntimeError("Home switch did not release during backoff")
            until = time.monotonic() + 2
            while not self.stopped and time.monotonic() < until:
                time.sleep(0.01)
            if not self.stopped:
                raise RuntimeError("Axis failed to stop after home backoff")
        finally:
            self._homing = False
            self.stop()

    def _set_raw_velocity(self, sps: float) -> None:
        with self._lock:
            self._target_sps = max(-self.max_sps, min(self.max_sps, sps))
            self._emergency.clear()

    def emergency_stop(self) -> None:
        self.stop()
        self._emergency.set()
        self._gpio[1].off()
        self._gpio[2].off()

    def _run(self) -> None:
        speed = 0.0
        last = time.monotonic()
        phase = 0.0
        while not self._closing.is_set():
            if self._emergency.is_set():
                speed = 0.0
                phase = 0.0
                with self._lock:
                    self._actual_sps = 0.0
                self._gpio[1].off()
                self._gpio[2].off()
                self._closing.wait(0.005)
                continue
            now = time.monotonic()
            dt = min(now - last, 0.05)
            last = now
            with self._lock:
                target = self._target_sps
                pos = self.position_steps
            if speed and target and speed * target < 0:
                target = 0.0  # ramp to rest before reversing
            speed += max(-self.accel * dt, min(self.accel * dt, target - speed))
            with self._lock:
                self._actual_sps = speed
            if abs(speed) < 1.0 and abs(target) < 1.0:
                speed = 0.0
                phase = 0.0
                self._gpio[2].off()
                self._closing.wait(0.005)
                continue
            direction = 1 if speed > 0 else -1
            next_pos = pos + direction
            if not self._homing and (next_pos < self.min_steps or next_pos > self.max_steps):
                self.stop()
                speed = 0.0
                self._fault = "Soft limit reached"
                continue
            if direction < 0 and self._home is not None and self._home.is_active and not self._homing:
                self.stop()
                speed = 0.0
                self._fault = "Home switch limit reached"
                continue
            direction_pin, step_pin, enable_pin = self._gpio
            enable_pin.on()  # tested HAT B enable polarity: high = enabled
            direction_pin.value = bool((direction > 0) != self.cfg.get("invert", False))
            phase += abs(speed) * dt
            while phase >= 1.0:
                step_pin.on()
                time.sleep(0.0005)
                step_pin.off()
                with self._lock:
                    self.position_steps += direction
                phase -= 1.0
            wait = max(0.0005, min(0.005, (1.0 - phase) / max(abs(speed), 1.0)))
            self._closing.wait(wait)
        self._gpio[1].off()
        self._gpio[2].off()

    def close(self) -> None:
        self.stop()
        self._closing.set()
        self._thread.join(timeout=2)
        if self._home:
            self._home.close()
        for device in self._gpio:
            device.off()
            device.close()


class MotionSystem:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        # GPIO4 has a pull-up at boot on this documented build; force both
        # HAT enables low before gpiozero claims them.
        subprocess.run(["pinctrl", "set", "12,4", "op", "dl"], check=True)
        switches = cfg.get("homing_switches_enabled", False)
        self.axes = {}
        try:
            self.axes["pan"] = Axis(
                "pan", cfg["pan"], cfg,
                cfg.get("home_pan_pin") if switches else None,
            )
            self.axes["tilt"] = Axis(
                "tilt", cfg["tilt"], cfg,
                cfg.get("home_tilt_pin") if switches else None,
            )
        except Exception:
            for axis in self.axes.values():
                axis.close()
            subprocess.run(["pinctrl", "set", "12,4", "op", "dl"], check=False)
            raise

    def stop(self) -> None:
        for axis in self.axes.values():
            axis.stop()

    def emergency_stop(self) -> None:
        for axis in self.axes.values():
            axis.emergency_stop()

    def clear_faults(self) -> None:
        for axis in self.axes.values():
            axis.clear_fault()

    def close(self) -> None:
        self.stop()
        for axis in self.axes.values():
            axis.close()
        subprocess.run(["pinctrl", "set", "12,4", "op", "dl"], check=False)

    def telemetry(self) -> dict:
        return {name: {"deg": axis.pos_deg, "calibrated": axis.calibrated,
                       "velocity_dps": axis.velocity_dps, "fault": axis.fault}
                for name, axis in self.axes.items()}
