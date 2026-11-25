"""Pure image geometry and bounded PID control."""
from __future__ import annotations

from dataclasses import dataclass


def pixel_error_to_degrees(error_px: float, fov_deg: float, pixels: int) -> float:
    if pixels <= 0:
        raise ValueError("pixels must be positive")
    return error_px * fov_deg / pixels


@dataclass
class PID:
    kp: float
    ki: float
    kd: float
    deadband: float
    limit: float
    integral_limit: float = 1000.0
    integral: float = 0.0
    last_error: float | None = None

    def update(self, error: float, dt: float) -> float:
        if dt <= 0:
            return 0.0
        if abs(error) <= self.deadband:
            self.integral = 0.0
            self.last_error = error
            return 0.0
        derivative = 0.0 if self.last_error is None else (error - self.last_error) / dt
        self.last_error = error
        candidate = max(-self.integral_limit,
                        min(self.integral_limit, self.integral + error * dt))
        raw = self.kp * error + self.ki * candidate + self.kd * derivative
        output = max(-self.limit, min(self.limit, raw))
        if abs(raw) <= self.limit or raw * error < 0:
            self.integral = candidate
        return output

    def reset(self) -> None:
        self.integral = 0.0
        self.last_error = None


class Aimer:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.pan_sign = 1 if cfg.get("pan_sign", 1) >= 0 else -1
        self.tilt_sign = 1 if cfg.get("tilt_sign", -1) >= 0 else -1
        self.pan = PID(cfg["kp"], cfg["ki"], cfg["kd"], cfg["deadband_px"], cfg["max_pan_dps"])
        self.tilt = PID(cfg["kp"], cfg["ki"], cfg["kd"], cfg["deadband_px"], cfg["max_tilt_dps"])

    def update(self, err_x: float, err_y: float, dt: float) -> tuple[float, float]:
        # Tune axis signs on the assembled frame; screen Y increases downward.
        return (self.pan_sign * self.pan.update(err_x, dt),
                self.tilt_sign * self.tilt.update(err_y, dt))

    def reset(self) -> None:
        self.pan.reset()
        self.tilt.reset()
