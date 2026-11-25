"""Latest-frame camera reader; dry-run uses a moving synthetic marker."""
from __future__ import annotations

import math
import os
import sys
import threading
import time

import cv2
import numpy as np

from .config import camera_config


class Capture:
    def __init__(self, simulation: bool):
        self.cfg = camera_config()
        self.simulation = simulation
        self._lock = threading.Lock()
        self._frame = None
        self._timestamp = 0.0
        self._error: str | None = None
        self._capture = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        if not simulation:
            if sys.platform == "win32":
                self._backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
            else:
                self._backend = cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else cv2.CAP_ANY
            backend_override = os.getenv("PRAHARI_CAMERA_BACKEND")
            if backend_override:
                self._backend = int(backend_override)
            self._error = f"Waiting for camera device {self.cfg['device']}"
        else:
            self._backend = cv2.CAP_ANY
        self._thread.start()

    def _open_camera(self) -> bool:
        try:
            capture = cv2.VideoCapture(self.cfg["device"], self._backend)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["width"])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["height"])
            capture.set(cv2.CAP_PROP_FPS, self.cfg["fps"])
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        except cv2.error as exc:
            self._error = f"Camera open failed: {exc}"
            return False
        if not capture.isOpened():
            capture.release()
            self._error = f"Could not open camera device {self.cfg['device']}; retrying"
            return False
        self._capture = capture
        self._error = None
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            if self.simulation:
                t = time.monotonic()
                frame = np.zeros((self.cfg["height"], self.cfg["width"], 3), dtype=np.uint8)
                x = int(self.cfg["width"] / 2 + math.sin(t * 0.45) * self.cfg["width"] * 0.25)
                cv2.circle(frame, (x, self.cfg["height"] // 2), 24, (0, 0, 255), -1)
                cv2.putText(frame, "SIMULATION - RED OBJECT", (12, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                self._publish(frame)
                self._stop.wait(1 / max(1, self.cfg["fps"]))
                continue
            if self._capture is None and not self._open_camera():
                self._stop.wait(0.5)
                continue
            try:
                ok, frame = self._capture.read()
            except cv2.error:
                ok, frame = False, None
            if not ok:
                self._error = "Camera frame read failed; reconnecting"
                self._capture.release()
                self._capture = None
                self._stop.wait(0.25)
                continue
            self._error = None
            self._publish(frame)

    def _publish(self, frame) -> None:
        with self._lock:
            self._frame = frame
            self._timestamp = time.monotonic()

    def latest(self):
        with self._lock:
            if self._frame is None:
                return None, 0.0
            return self._frame.copy(), self._timestamp

    @property
    def status(self) -> dict:
        _, stamp = self.latest()
        age_ms = round((time.monotonic() - stamp) * 1000, 1) if stamp else None
        fresh = age_ms is not None and age_ms <= self.cfg["stale_ms"]
        error = self._error or (None if fresh else "No fresh camera frames")
        return {"available": fresh, "age_ms": age_ms, "error": error,
                "simulation": self.simulation}

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        if self._capture:
            self._capture.release()
