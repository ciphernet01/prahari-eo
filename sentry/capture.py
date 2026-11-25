"""Latest-frame reader for the configured physical camera."""
from __future__ import annotations

import os
import sys
import threading
import time

import cv2

from .config import camera_config


class Capture:
    def __init__(self):
        self.cfg = camera_config()
        self._lock = threading.Lock()
        self._frame = None
        self._timestamp = 0.0
        self._error: str | None = None
        self._capture = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._open_camera()
        self._thread.start()

    def _open_camera(self) -> None:
        if sys.platform == "win32":
            backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
        else:
            backend = cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else cv2.CAP_ANY
        backend_override = os.getenv("PRAHARI_CAMERA_BACKEND")
        if backend_override:
            backend = int(backend_override)
        capture = cv2.VideoCapture(self.cfg["device"], backend)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["width"])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["height"])
        capture.set(cv2.CAP_PROP_FPS, self.cfg["fps"])
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        if not capture.isOpened():
            capture.release()
            self._capture = None
            self._error = f"Could not open camera device {self.cfg['device']}"
            return
        self._capture = capture
        self._error = None

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._capture is None or not self._capture.isOpened():
                self._error = f"Could not open camera device {self.cfg['device']}"
                self._open_camera()
                if self._capture is None:
                    self._stop.wait(1)
                continue
            ok, frame = self._capture.read()
            if not ok:
                self._error = "Camera frame read failed"
                self._capture.release()
                self._capture = None
                self._stop.wait(0.05)
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
        available = age_ms is not None and age_ms <= self.cfg["stale_ms"]
        return {"available": available, "age_ms": age_ms, "error": self._error}

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        if self._capture:
            self._capture.release()
