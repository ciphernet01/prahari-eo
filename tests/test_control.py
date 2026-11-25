import pytest

from sentry.control import PID, pixel_error_to_degrees


def test_pixel_geometry_is_zero_at_center_and_signed():
    assert pixel_error_to_degrees(0, 55, 640) == 0
    assert pixel_error_to_degrees(320, 55, 640) == pytest.approx(27.5)
    assert pixel_error_to_degrees(-320, 55, 640) == pytest.approx(-27.5)


def test_pid_deadband_and_output_limit():
    pid = PID(kp=1.0, ki=0.0, kd=0.0, deadband=5, limit=20)
    assert pid.update(4, 0.1) == 0
    assert pid.update(50, 0.1) == 20
    assert pid.update(-50, 0.1) == -20


def test_pid_reset_clears_derivative_memory():
    pid = PID(kp=0.0, ki=0.0, kd=1.0, deadband=0, limit=100)
    pid.update(4, 0.1)
    assert pid.update(6, 0.1) == pytest.approx(20)
    pid.reset()
    assert pid.update(6, 0.1) == 0


def test_geometry_rejects_bad_resolution():
    with pytest.raises(ValueError):
        pixel_error_to_degrees(10, 55, 0)
