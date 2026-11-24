"""Physical-interlock state machine and the sole high-level actuator owner."""
from __future__ import annotations

from enum import Enum
import threading
import time

from .config import config
from .control import Aimer
from .fire import Buzzer
from .motion import MotionSystem
from .types import Target


class State(str, Enum):
    BOOT = "BOOT"
    HOMING = "HOMING"
    SAFE = "SAFE"
    ARMED = "ARMED"
    TRACKING = "TRACKING"
    LOCKED = "LOCKED"  # buzzer-only object-lock indication
    FAULT = "FAULT"


class SafetyController:
    def __init__(self, motion: MotionSystem, buzzer: Buzzer, simulation: bool,
                 camera_timeout_ms: int, event_log):
        self.motion = motion
        self.buzzer = buzzer
        self.simulation = simulation
        self.camera_timeout = camera_timeout_ms / 1000
        self.log = event_log
        self.state = State.BOOT
        self.mode = "manual"
        self.target: Target | None = None
        self.err_x = self.err_y = 0.0
        self.lock_frames = 0
        self._lock_notified = False
        self._camera_last = time.monotonic()
        self._jog_last = 0.0
        self._estop = False
        self._fault: str | None = None
        self._lock = threading.RLock()
        self._arm_enabled = False
        self._deadman_held = False
        self._deadman_last = 0.0
        self.aimer = Aimer(config["control"])
        self._last_control = time.monotonic()
        self._transition(State.SAFE, "startup complete")

    @property
    def arm_on(self) -> bool:
        return self._arm_enabled

    @property
    def deadman_on(self) -> bool:
        timeout = config["safety"]["deadman_timeout_ms"] / 1000
        return self._deadman_held and time.monotonic() - self._deadman_last <= timeout

    def set_arm(self, enabled: bool) -> None:
        with self._lock:
            if enabled:
                if self._estop or self._fault:
                    raise RuntimeError("Disarm once to acknowledge the e-stop/fault before arming")
                if not all(axis.calibrated for axis in self.motion.axes.values()):
                    raise RuntimeError("Calibrate both axes before arming")
                self._arm_enabled = True
                self._transition(State.ARMED, "dashboard ARM enabled")
                self.log.write("software_arm", enabled=True)
            else:
                self._arm_enabled = False
                self._deadman_held = False
                self._estop = False
                self._fault = None
                self.motion.clear_faults()
                self._safe_outputs()
                self.mode = "manual"
                self._transition(State.SAFE, "dashboard ARM disabled / reset")
                self.log.write("software_arm", enabled=False)

    def set_deadman(self, held: bool) -> None:
        with self._lock:
            if held and (not self.arm_on or self._estop or self._fault):
                raise RuntimeError("ARM must be enabled before holding the dead-man control")
            self._deadman_held = held
            self._deadman_last = time.monotonic()
            if not held:
                self.buzzer.off()

    def _transition(self, state: State, reason: str) -> None:
        if self.state != state:
            prior = self.state
            self.state = state
            self.log.write("state", previous=prior.value, state=state.value, reason=reason)

    def _safe_outputs(self) -> None:
        self.motion.emergency_stop()
        self.buzzer.off()
        self.aimer.reset()

    def estop(self) -> None:
        with self._lock:
            self._estop = True
            self._arm_enabled = False
            self._deadman_held = False
            self._safe_outputs()
            self._transition(State.SAFE, "software e-stop latched")
            self.log.write("estop")

    def tick(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._estop:
                self._safe_outputs()
                self._transition(State.SAFE, "e-stop")
                return
            if self._fault:
                self._safe_outputs()
                self._transition(State.FAULT, self._fault)
                return
            axis_fault = next((axis.fault for axis in self.motion.axes.values() if axis.fault), None)
            if axis_fault:
                self._trip(axis_fault)
                return
            if now - self._camera_last > self.camera_timeout:
                self._trip("camera watchdog")
                return
            if not self.arm_on:
                self._safe_outputs()
                self.mode = "manual"
                self._transition(State.SAFE, "dashboard ARM disabled")
                return
            if not all(axis.calibrated for axis in self.motion.axes.values()):
                self._safe_outputs()
                self._transition(State.SAFE, "axes need calibration")
                return
            if self.state in (State.SAFE, State.BOOT):
                self._transition(State.ARMED, "dashboard ARM enabled")
            if self.mode == "manual":
                if now - self._jog_last > config["safety"]["jog_timeout_ms"] / 1000:
                    self.motion.stop()
                self._transition(State.ARMED, "manual mode")
                return
            if self.mode == "auto":
                if self.state not in (State.TRACKING, State.LOCKED):
                    self._transition(State.TRACKING, "automatic object tracking")
                if self.target is None:
                    self.motion.stop()
                    self.buzzer.off()
                    self.lock_frames = 0
                    self._lock_notified = False
                    self._transition(State.TRACKING, "target lost")
                    return
                self.lock_frames += 1
                if abs(self.err_x) <= config["safety"]["lock_tolerance_px"] and \
                   abs(self.err_y) <= config["safety"]["lock_tolerance_px"]:
                    if self.lock_frames >= config["safety"]["lock_frames_required"] and self.deadman_on:
                        self.motion.stop()
                        self._transition(State.LOCKED, "object centred; dashboard dead-man held")
                        if not self._lock_notified:
                            if self.buzzer.pulse(config["safety"]["buzzer_pulse_ms"],
                                                 config["safety"]["buzzer_cooldown_s"]):
                                self.log.write("buzzer_lock_indication", err_x=self.err_x, err_y=self.err_y)
                            self._lock_notified = True
                        return
                else:
                    self.lock_frames = 0
                    self._lock_notified = False
                    if self.state == State.LOCKED:
                        self.buzzer.off()
                        self._transition(State.TRACKING, "marker left lock tolerance")
                if not self.deadman_on and self.state == State.LOCKED:
                    self.buzzer.off()
                    self._lock_notified = False
                    self._transition(State.TRACKING, "dashboard dead-man released")
                dt = min(0.1, max(0.001, now - self._last_control))
                self._last_control = now
                pan, tilt = self.aimer.update(self.err_x, self.err_y, dt)
                self.motion.axes["pan"].set_velocity_dps(pan)
                self.motion.axes["tilt"].set_velocity_dps(tilt)

    def _trip(self, reason: str) -> None:
        if self._fault == reason:
            return
        self._fault = reason
        self._arm_enabled = False
        self._deadman_held = False
        self._safe_outputs()
        self._transition(State.FAULT, reason)
        self.log.write("fault", reason=reason)

    def trip_fault(self, reason: str) -> None:
        with self._lock:
            self._trip(reason)

    def set_target(self, target: Target | None, err_x: float = 0.0, err_y: float = 0.0) -> None:
        with self._lock:
            self._camera_last = time.monotonic()
            self.target = target
            self.err_x, self.err_y = err_x, err_y
            if target is None:
                self.lock_frames = 0
                if self.mode == "auto":
                    self.motion.stop()
                    self.aimer.reset()
            self.tick()

    def calibrate(self) -> None:
        with self._lock:
            if self.arm_on or self._estop:
                raise RuntimeError("Calibration requires dashboard ARM off and no e-stop")
            self.motion.stop()
            for axis in self.motion.axes.values():
                axis.mark_zero()
            self._fault = None
            self.log.write("manual_calibration")

    def home(self) -> None:
        with self._lock:
            if self.arm_on:
                raise RuntimeError("Switch dashboard ARM off before homing")
            if self._estop or self._fault:
                raise RuntimeError("Acknowledge the fault/e-stop before homing")
            self.motion.stop()
            self._transition(State.HOMING, "operator requested homing; dashboard ARM off")
            try:
                for axis in self.motion.axes.values():
                    axis.home(config["safety"]["home_timeout_s"])
            except RuntimeError as exc:
                if "not configured" not in str(exc):
                    self._trip(f"homing: {exc}")
                raise
            self._fault = None
            self._transition(State.SAFE, "homing complete")
            self.log.write("homing_complete")

    def jog(self, pan_dps: float, tilt_dps: float) -> None:
        with self._lock:
            if self.state != State.ARMED or self.mode != "manual" or not self.arm_on or \
               self._estop or self._fault:
                raise RuntimeError("Select JOG after calibrating both axes")
            self.motion.axes["pan"].set_velocity_dps(pan_dps)
            self.motion.axes["tilt"].set_velocity_dps(tilt_dps)
            self._jog_last = time.monotonic()

    def set_mode(self, mode: str) -> None:
        if mode not in ("idle", "manual", "auto"):
            raise ValueError("mode must be idle, manual, or auto")
        with self._lock:
            if mode == "idle":
                self._arm_enabled = False
                self._deadman_held = False
                self.motion.stop()
                self.buzzer.off()
                self.aimer.reset()
                self.mode = "manual"
                if not self._estop and not self._fault:
                    self._transition(State.SAFE, "operator selected IDLE")
                self.log.write("mode", mode="idle")
                return
            if self._estop or self._fault:
                raise RuntimeError("E-stop/fault is latched; restart the service after resolving it")
            if not all(axis.calibrated for axis in self.motion.axes.values()):
                raise RuntimeError("Calibrate both axes before selecting JOG or AUTO")
            self.motion.stop()
            self.aimer.reset()
            self.lock_frames = 0
            self._arm_enabled = True
            self.mode = mode
            self._transition(State.ARMED if mode == "manual" else State.TRACKING,
                             f"operator selected {mode.upper()}")
            self.log.write("mode", mode=mode)

    def telemetry(self) -> dict:
        with self._lock:
            return {"state": self.state.value, "mode": self.mode,
                    "interlocks": {"arm_enabled": self.arm_on, "deadman": self.deadman_on,
                                   "estop": self._estop},
                    "axes": self.motion.telemetry(),
                    "target": self.target.as_dict() if self.target else None,
                    "err_x": self.err_x, "err_y": self.err_y,
                    "lock_frames": self.lock_frames, "fault": self._fault}

    def close(self) -> None:
        self._safe_outputs()
