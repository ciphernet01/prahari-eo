import cv2
import numpy as np
import pytest

from sentry.detect import Detector


def test_color_detector_finds_designated_red_marker():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(frame, (410, 220), 30, (0, 0, 255), -1)
    target = Detector("color").detect(frame)
    assert target is not None
    assert target.x == pytest.approx(410, abs=1)
    assert target.y == pytest.approx(220, abs=1)
    assert target.w >= 55 and target.h >= 55
