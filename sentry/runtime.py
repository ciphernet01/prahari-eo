from __future__ import annotations

import os
import subprocess
import threading
import time

import cv2

from .capture import Capture
from .config import config
from .control import pixel_error_to_degrees
from .detect import Detector
from .fire import Buzzer
from .logger import EventLog
from .motion import MotionSystem
from .safety import SafetyController


class Runtime:
    def __init__(self):
        self.simulation = config["runtime"]["simulation"]
        self.log = EventLog(config["safety"]["event_log"])
        # Outputs are made safe before camera or web service initialization.
        self.buzzer = Buzzer(config["safety"]["relay_pin"],
                             config["safety"]["relay_active_low"],
                             config["safety"]["buzzer_enabled"], self.simulation)
        try:
            self.motion = MotionSystem(config["motors"], self.simulation)
            self.safety = SafetyController(self.motion, self.buzzer, self.simulation,
                                           config["camera"]["stale_ms"], self.log)
        except Exception:
            self.buzzer.close()
            raise
        camera_sim = self.simulation and os.getenv("PRAHARI_CAMERA_SIM", "1") == "1"
        self.camera = Capture(camera_sim)
        self.detector = Detector()
        self._thread = None
        self._stop = threading.Event()
        self._display_lock = threading.Lock()
        self._display = None
        self._last_processed = 0.0
        self._fps = 0.0
        self._latency_ms = 0.0
        self._throttled = False
        self._throttle_flags_hex = None
        self._cpu_temp = None
        self._angular_error = {"pan": 0.0, "tilt": 0.0}
        self._last_system_read = 0.0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vision-safety", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            frame, stamp = self.camera.latest()
            if frame is not None and stamp != self._last_processed:
                try:
                    target = self.detector.detect(frame)
                    h, w = frame.shape[:2]
                    err_x = (target.x - w / 2) if target else 0.0
                    err_y = (target.y - h / 2) if target else 0.0
                    self._angular_error = {
                        "pan": pixel_error_to_degrees(err_x, config["camera"]["fov_h_deg"], w),
                        "tilt": pixel_error_to_degrees(err_y, config["camera"]["fov_v_deg"], h),
                    }
                    self.safety.set_target(target, err_x, err_y)
                    with self._display_lock:
                        self._display = frame
                    self._last_processed = stamp
                    elapsed = max(1e-6, time.monotonic() - started)
                    self._fps = 0.9 * self._fps + 0.1 / elapsed if self._fps else 1 / elapsed
                    self._latency_ms = (time.monotonic() - stamp) * 1000
                except Exception as exc:
                    self.safety.trip_fault(f"vision pipeline: {exc}")
            self.safety.tick()
            self._read_system_status()
            self._stop.wait(0.01)

    def _read_system_status(self) -> None:
        now = time.monotonic()
        if now - self._last_system_read < 5:
            return
        self._last_system_read = now
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", encoding="ascii") as f:
                self._cpu_temp = int(f.read().strip()) / 1000
        except (OSError, ValueError):
            self._cpu_temp = None
        try:
            result = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                    text=True, timeout=1, check=False)
            value = result.stdout.strip().split("=")[-1]
            self._throttle_flags_hex = f"0x{int(value, 16):08x}"
            self._throttled = int(value, 16) != 0
            if self._throttled:
                self.safety.trip_fault(f"Pi reported throttled flags {value}")
        except (OSError, subprocess.SubprocessError, ValueError):
            self._throttled = False
            self._throttle_flags_hex = None

    def jpeg(self) -> bytes | None:
        with self._display_lock:
            frame = None if self._display is None else self._display.copy()
        if frame is None:
            frame, _ = self.camera.latest()
        if frame is None:
            return None
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpeg.tobytes() if ok else None

    def telemetry(self) -> dict:
        return {**self.safety.telemetry(), "camera": self.camera.status,
                "angular_error_deg": self._angular_error,
                "fps": round(self._fps, 1), "latency_ms": round(self._latency_ms, 1),
                "cpu_temp_c": self._cpu_temp, "throttled": self._throttled,
                "throttle_flags_hex": self._throttle_flags_hex,
                "simulation": self.simulation}

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.safety.close()
        self.camera.close()
        self.motion.close()
        self.buzzer.close()
        self.log.close()
