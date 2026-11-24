"""Designated-object detectors. No people or face models are used."""
from __future__ import annotations

import cv2
import numpy as np

from .config import detector_config
from .types import Target


class Detector:
    def __init__(self, backend: str | None = None):
        cfg = detector_config()
        self.backend = backend or cfg.get("backend", "color")
        self.cfg = cfg
        self._mog = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=32,
                                                        detectShadows=True)

    def detect(self, frame: np.ndarray) -> Target | None:
        if self.backend == "color":
            return self._color(frame)
        if self.backend == "aruco":
            return self._aruco(frame)
        if self.backend == "motion":
            return self._motion(frame)
        raise ValueError(f"Unknown detector backend: {self.backend}")

    def _largest(self, mask: np.ndarray, min_area: float) -> Target | None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        if area < min_area:
            return None
        x, y, w, h = cv2.boundingRect(contour)
        return Target(x + w / 2, y + h / 2, w, h,
                      confidence=min(1.0, area / max(min_area * 4, 1)))

    def _color(self, frame: np.ndarray) -> Target | None:
        c = self.cfg["color"]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        if c["h_min"] <= c["h_max"]:
            mask = cv2.inRange(hsv, (c["h_min"], c["s_min"], c["v_min"]),
                               (c["h_max"], 255, 255))
        else:
            lo = cv2.inRange(hsv, (0, c["s_min"], c["v_min"]), (c["h_max"], 255, 255))
            hi = cv2.inRange(hsv, (c["h_min"], c["s_min"], c["v_min"]), (179, 255, 255))
            mask = cv2.bitwise_or(lo, hi)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return self._largest(mask, c["min_area"])

    def _aruco(self, frame: np.ndarray) -> Target | None:
        if not hasattr(cv2, "aruco"):
            raise RuntimeError("ArUco requires OpenCV with the contrib modules")
        a = self.cfg["aruco"]
        dictionary = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, a["dictionary"]))
        corners, ids, _ = cv2.aruco.detectMarkers(frame, dictionary)
        if ids is None:
            return None
        for points, marker_id in zip(corners, ids.flatten()):
            if int(marker_id) == int(a["id"]):
                points = points.reshape(4, 2)
                x0, y0 = points.min(axis=0)
                x1, y1 = points.max(axis=0)
                return Target((x0 + x1) / 2, (y0 + y1) / 2,
                              x1 - x0, y1 - y0, 1.0)
        return None

    def _motion(self, frame: np.ndarray) -> Target | None:
        c = self.cfg["motion"]
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)
        mask = self._mog.apply(blurred)
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, None, iterations=2)
        return self._largest(mask, c["min_area"])


def overlay(frame: np.ndarray, target: Target | None) -> np.ndarray:
    shown = frame.copy()
    h, w = shown.shape[:2]
    cv2.drawMarker(shown, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 16, 1)
    if target:
        x, y = int(target.x), int(target.y)
        cv2.rectangle(shown, (int(x-target.w/2), int(y-target.h/2)),
                      (int(x+target.w/2), int(y+target.h/2)), (0, 220, 0), 2)
        cv2.circle(shown, (x, y), 4, (0, 220, 0), -1)
    return shown
