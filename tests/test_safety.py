import time

from sentry.safety import SafetyController, State
from sentry.types import Target


class FakeAxis:
    def __init__(self):
        self.calibrated = True
        self.fault = None
        self.velocity = 0

    def set_velocity_dps(self, velocity):
        self.velocity = velocity

    def stop(self):
        self.velocity = 0


class FakeMotion:
    def __init__(self):
        self.axes = {"pan": FakeAxis(), "tilt": FakeAxis()}
        self.stopped = False

    def stop(self):
        self.stopped = True
        for axis in self.axes.values():
            axis.stop()

    def emergency_stop(self):
        self.stop()

    def clear_faults(self):
        pass


class FakeBuzzer:
    def __init__(self):
        self.pulses = 0

    def off(self):
        pass

    def pulse(self, duration_ms, cooldown_s):
        self.pulses += 1
        return True


class FakeLog:
    def write(self, *args, **kwargs):
        pass


def make_safety(*, arm=True, deadman=False):
    motion, buzzer = FakeMotion(), FakeBuzzer()
    safety = SafetyController(motion, buzzer, 500, FakeLog())
    safety._camera_last = time.monotonic()
    if arm:
        safety.set_arm(True)
    if deadman:
        safety.set_deadman(True)
    safety.tick()
    return safety, motion, buzzer


def test_manual_jog_requires_dashboard_arm():
    safety, motion, _ = make_safety(arm=True)
    assert safety.state == State.ARMED
    safety.jog(10, -5)
    assert motion.axes["pan"].velocity == 10
    assert motion.axes["tilt"].velocity == -5


def test_e_stop_latches_until_dashboard_disarm_reset():
    safety, motion, _ = make_safety(arm=True)
    safety.estop()
    safety.tick()
    assert safety._estop is True
    assert motion.stopped
    safety.set_arm(False)
    assert safety._estop is False
    assert safety.state == State.SAFE


def test_buzzer_lock_requires_deadman_and_only_pulses_once(monkeypatch):
    safety, _, buzzer = make_safety(arm=True, deadman=True)
    safety.set_mode("auto")
    for _ in range(15):
        safety.set_target(Target(320, 240, 40, 40), 0, 0)
    assert safety.state == State.LOCKED
    assert buzzer.pulses == 1
    for _ in range(5):
        safety.set_target(Target(320, 240, 40, 40), 0, 0)
    assert buzzer.pulses == 1
