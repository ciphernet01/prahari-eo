# PRAHARI: Agent Build Spec

Vision-guided pan-tilt camera prototype on a Raspberry Pi 5. The optional output is a relay-switched buzzer. Latest EO-C2 direction supersedes the earlier software-switch design: ARM and dead-man must be physical, read-only interlocks with no browser ARM/dead-man endpoints or controls. Current backend and wiring have not implemented or mapped these inputs; until that gap is closed, the dashboard must report them unavailable and inhibit motion.

---

## 0. Rules for the agent (read first)

1. Read this whole file before writing code.
2. The hardware facts in section 3 were **verified on the bench**. Do not "correct" them from generic datasheets or memory. In particular, the motor enable pin is **active HIGH** on this HAT.
3. Anything that moves a motor or switches the relay must go through `safety.py`. Every hardware module must also run with `--dry-run` / `PRAHARI_SIM=1` (no GPIO, fake camera) so you can test without the device.
4. Never run motor tests unattended. Ask the human to confirm: 12V is on, nothing is attached to the shafts (or the frame is clear), and a hand is near the 12V switch.
5. **Out of scope. Do not add:**
   - any projectile, launcher, gel blaster, dart or laser control;
   - face, person or animal detection models;
   - any direct buzzer command or any internet-exposed control. The local token-protected dashboard may arm/disarm and hold the dead-man control; no command may bypass the marker-lock gate.
6. Keep modules small, typed, and documented. Pure logic (PID, geometry, state machine) needs pytest tests.
7. State your assumptions in the PR/commit message, and list anything you could not verify.

---

## 1. Scope

| In scope | Out of scope |
| --- | --- |
| Track a designated **object target** (toy robot / doll with a colour patch or ArUco marker) | Weapons, projectiles, autonomous firing |
| Two-axis aiming with stepper motors, PID, soft limits, homing | Face / person detection |
| Simulated trigger: relay switches a buzzer | Internet-exposed control |
| Local dashboard with software ARM, jog, dead-man hold and e-stop | Direct buzzer command or remote/public access |

---

## 2. Reference paper (what to borrow and what not to)

**Paper:** Andrianto, Aji, Susanthi, "Prototipe Sistem Sentry Gun Berbasis Raspberry Pi", *EPSILON J. Electrical Eng. and Information Technology*, Vol. 24 No. 1, June 2026, pp. 28-39.

The paper uses a Raspberry Pi 3B+, a Logitech C310 and a stepper HAT with two steppers on a pan/tilt frame, and a relay as the on/off switch of a toy dart blaster.

**Borrow:**
- **Detection pipeline for the optional motion backend:** Gaussian Mixture Model background subtraction (`cv2.createBackgroundSubtractorMOG2`), then edge/contour detection, bounding box (width and height), centre point, region-of-interest overlay, then convert the pixel offset to motor steps.
- **Two modes:** manual (W/A/S/D to move) and automatic (track).
- **Start-up calibration:** the operator jogs the axes to set the zero position.
- **Test protocol:** 10 trials per condition, at 1 m, 2 m and 3 m, in bright (about 140 lux) and dim (about 15 lux) light, target speed 0.1-1 m/s. The paper reports 85-100% movement success per condition (Table 1).
- **A simple operator console** with live video.

**Do not copy:**
- Buzzer activation from detection alone. Here the buzzer requires dashboard ARM, a held dashboard dead-man control, and a stable marker lock.
- Any dart or blaster wiring. The relay switches the **buzzer** only.
- Targeting people. The paper's demo shows a person; this project tracks designated objects.
- The paper's use of GPIO 22 for the relay. On this HAT GPIO 22 is a motor-2 mode pin (see section 3.3).

**Known weakness of motion-only detection:** background subtraction cannot track a target that stops moving, and it locks onto anything that moves. So the default backend here is colour or ArUco. The motion backend is for development and tests only.

---

## 3. Hardware (verified)

### 3.1 Parts

| Item | Detail |
| --- | --- |
| Computer | Raspberry Pi 5, Raspberry Pi OS **Trixie** (Debian 13), 64-bit, hostname `turret-pi`, user `dtc` |
| Motor HAT | Waveshare Stepper Motor HAT (B), SKU 22311, **HR8825** drivers (DRV8825-compatible) |
| Motors | 2 x NEMA 17 **JK42HS60-1704**: 1.8 deg (200 steps/rev), 1.7 A/phase, 3 ohm, 6.2 mH, 7.3 kg.cm, 4-wire bipolar |
| Camera | Logitech C525 USB webcam, `/dev/video0`, MJPG 640x480 |
| Trigger | Relay module (type to be confirmed: single channel, active-low or high) switching a buzzer |
| Power | 12 V 5 A supply into the HAT DC jack |
| Frame | Laminated MDF base and plates, aluminium angle tilt cradle (direct drive, no gearing) |

### 3.2 Motor wiring (verified)

Datasheet colours: black = A+, green = A-, red = B+, blue = B-. Coil pairs are black+green and red+blue.

| Terminal (top to bottom) | Motor 1 (pan) | Terminal | Motor 2 (tilt) |
| --- | --- | --- | --- |
| A1 | Black | A3 | Black |
| B1 | Red | B3 | Red |
| A2 | Green | A4 | Green |
| B2 | Blue | B4 | Blue |

Swapping the two wires inside one pair only reverses direction. Use `invert=True` in config instead of rewiring.

### 3.3 GPIO map (BCM numbering, gpiochip0 = `pinctrl-rp1`)

| Function | Motor 1 (pan) | Motor 2 (tilt) |
| --- | --- | --- |
| DIR | 13 | 24 |
| STEP | 19 | 18 |
| ENABLE | 12 | 4 |
| Mode pins (not used, DIP switches set microstepping) | 16, 17, 20 | 21, 22, 27 |

Pins used by the HAT: 4, 12, 13, 16, 17, 18, 19, 20, 21, 22, 24, 27. **Do not reuse them.**

Proposed pins for the rest (not yet wired, confirm with the human):

| Function | GPIO | Notes |
| --- | --- | --- |
| Relay input (output) | 26 | default OFF at boot; add a pull resistor if the module clicks at power-up |
| Pan home switch | 23 | pull-up, active low (not yet fitted) |
| Tilt home switch | 25 | pull-up, active low (not yet fitted) |

### 3.4 Verified behaviour (do not contradict)

1. **Enable pin is active HIGH.** High = driver on, low = off. Confirmed by the manufacturer's own `HR8825.py` (`TurnStep` writes enable high, `Stop` writes it low) and by bench observation.
2. **GPIO 4 has a pull-up at boot,** so motor 2 is energised (whining, shaft held) until software drives it low. Run `pinctrl set 12,4 op dl` at startup, and again **after** every program exit (releasing a GPIO returns it to its default pull).
3. **Microstepping:** hardware mode, DIP switches S0-S5. Full-step = all 0. **1/16 = S0,S1,S2 = 0,0,1 and S3,S4,S5 = 0,0,1.** The board silkscreen shows 0 at the top and 1 at the bottom. The mode GPIO pins must **not** be driven (the six solder resistors are not fitted). Steps per revolution at 1/16 = **3200**, so 8.889 steps per degree.
4. **Current limit:** the factory pot setting is about 1.4 V, which is about 1.4 A (current in amps equals Vref in volts, 0.2 ohm sense resistors). Target about 1.1 V. Never turn the pot fully counter-clockwise (about 3.3 A, above the chip rating). The pot adjuster is plastic; Vref is read at the middle solder leg of the pot, against the GND terminal.
5. **HAT power switch ON** is required for the motors to run. With the switch ON the HAT's 5 V regulator also feeds the Pi's header. Verified bench setup: **HAT switch ON, Pi USB-C unplugged, 12 V on.** Never plug the Pi's USB-C in while the switch is ON (the manufacturer's demo notes disagree, so it is untested and not allowed here).
6. **Speed:** the official demo runs full-step at 0.005 s per half-pulse. 1/16 microstepping was tested at 0.002 s, and at faster delays down to 0.0005 s (1000 steps/s) with no missed steps reported. Treat 1000 steps/s (about 112 deg/s) as the working ceiling until measured more.
7. **Libraries:** the Pi 5 needs `lgpio` (via `gpiozero`'s lgpio backend). **pigpio, RPi.GPIO, wiringPi and bcm2835 do not work.** The official, working reference is `~/Stepper_Motor_HAT_B_Code/Raspberry PI/python-gpiozero/HR8825.py`.
8. **Under-voltage watch:** the Pi runs from the HAT's regulator (about 3 A limit). Log `vcgencmd get_throttled` during camera + motor runs, and treat any non-zero flag as a fault to report.

---

## 4. Software environment

- Python 3.13 on Trixie. System packages are installed: `python3-opencv`, `python3-numpy`, `python3-lgpio`, `python3-yaml`, `v4l-utils`, `git`.
- Use the venv `~/turret-env` created with `--system-site-packages` (so apt's OpenCV and lgpio are visible). `pip install` goes there, never system-wide.
- Project root: `~/turret`.
- Planned extra packages: `fastapi`, `uvicorn[standard]`, `pytest`.
- Network: the Pi joins the room Wi-Fi (also reachable over the direct Ethernet cable at its link-local IPv6 address). Allow for DHCP address changes; use the hostname `turret-pi.local` where possible.

---

## 5. Current status

| Item | Status |
| --- | --- |
| Pi 5 OS, SSH, VNC (wayvnc), Wi-Fi | Done |
| Camera capture (`tests/cam_test.py`) | Done (snapshot saved; FPS figure not recorded) |
| Motors: manufacturer demo, full-step and 1/16 speed tests | Done, both motors pass |
| `src/motion.py` (`Axis` class, appendix A) | **Written, hardware test result not yet reported** |
| Homing / limit switches | Not fitted yet |
| Frame (MDF / sunboard / aluminium) | Parts being made |
| Detection, tracking, PID, safety, relay, API, dashboard | **To build** |

---

## 6. Repository layout

```
turret/
  README.md
  config.yaml
  requirements.txt
  src/
    motion.py        # Axis class: step generation, soft limits, homing
    capture.py       # threaded camera reader (latest frame only)
    detect.py        # backends: color, aruco, motion (MOG2)
    control.py       # PID: pixel error -> deg/s
    safety.py        # dashboard ARM/dead-man state, e-stop, state machine, watchdogs
    fire.py          # relay output, pulse, cooldown, interlock check
    server.py        # FastAPI: video, telemetry WebSocket, commands
    logger.py
    sim.py           # fake camera, fake GPIO, for --dry-run
    main.py
  tests/
    test_control.py  test_safety.py  test_geometry.py   # pure logic, pytest
    cam_test.py  motion_test.py  bench_*.py              # hardware, human-run
  web/               # built dashboard files (frontend teammate)
```

---

## 7. Module specifications

### 7.1 `motion.py`
- One `Axis` per motor, running its own thread. The reference implementation is in appendix A.
- API: `set_velocity_dps()`, `move_to_deg()`, `stop()`, `pos_deg`, `home()`, `close()`.
- Enable pin high to run, low when idle (disable after about 2 s idle). On `close()` drive both enables low through `pinctrl`.
- Soft limits are enforced inside the step loop, never only by the caller.
- Reverse through zero speed (no instant reversal). Acceleration-limited.
- `home()`: drive slowly towards the home switch, back off, set `pos = 0`. Until switches are fitted, position zero is wherever the operator calibrates it (see 7.5).
- Pan limits start at -45..+45 deg, tilt at -20..+30 deg (edit in config).

### 7.2 `capture.py`
- Thread reads from `/dev/video0` with OpenCV V4L2, **MJPG 640x480**, `BUFFERSIZE=1`. Always hand out the newest frame, never a queue.
- Turn autofocus off (`v4l2-ctl -d /dev/video0 --set-ctrl=focus_automatic_continuous=0`, then set a fixed focus once the camera is mounted).
- Expose frame timestamp. If no frame for 500 ms, raise a camera fault.

### 7.3 `detect.py`
Common interface: `detect(frame) -> Target | None` where `Target = {x, y, w, h, conf}` (pixel centre and box).

Backends, selected in config:
1. `color` (default): HSV threshold, morphological open/close, largest contour above a minimum area, centre of the box.
2. `aruco`: `cv2.aruco` marker with a given ID; centre of the marker.
3. `motion` (dev only): `createBackgroundSubtractorMOG2` (history about 500, a tunable variance threshold, shadow detection on), blur, threshold, dilate, contours, largest box above a minimum area. Follow the paper's order: background subtraction, edges, width/height, ROI, centre.

Run detection in its own thread or every Nth frame, with a CSRT/KCF tracker between detections if CPU-limited. No face or person models.

### 7.4 `control.py`
- Geometry: C525 horizontal field of view is about 55 deg and vertical about 41 deg at 640x480 (the lens is 69 deg diagonal; **approximate, calibrate by measurement**). `deg_per_px = fov / resolution`.
- PID per axis: input = pixel error from the frame centre, output = velocity in deg/s, clamped to `max_dps`. Starting gains (tune on hardware): `kp = 0.12`, `ki = 0`, `kd = 0.01`, deadband 6 px, output limit 60 deg/s, anti-windup on the integrator.
- Target lost: decay the velocity to zero within about 300 ms (do not coast).
- Pure functions; unit-tested.

### 7.5 `safety.py`
- Inputs: dashboard ARM state, dashboard dead-man hold with 300 ms heartbeat timeout, software e-stop flag, camera watchdog, and motion fault.
- Owns the state machine (section 8) and is the **only** module allowed to enable motors or the relay.
- Start disarmed. Dashboard ARM is accepted only after both axes are calibrated; disarming also acknowledges a latched software e-stop/fault.
- Start-up calibration (until home switches are fitted): with ARM off, the operator centers both axes and confirms; that position becomes zero.
- Hold-to-move jog: motion command expires 300 ms after the last message.

### 7.6 `fire.py`
- Relay output (GPIO 26), default OFF, set to the OFF level before anything else at start-up.
- `pulse()` allowed only when `safety` reports `LOCKED`. Pulse 300 ms, cooldown 2 s, optional maximum pulses per arm session.
- There is no direct buzzer command. Safety may pulse only the buzzer after stable marker lock while dashboard ARM and dead-man are active. Relay output remains disabled by default.
- Active-low or active-high comes from config (to be confirmed by the human).

### 7.7 `server.py` and `web/`
See section 10. The API exposes video, telemetry, authenticated ARM/dead-man, hold-to-move jog, mode, e-stop, config and the event log. It has no direct buzzer or e-stop-clear command.

### 7.8 `logger.py`
JSON lines, rotating files: state changes, simulated shots (target error at trigger time), faults, throttle flags.

---

## 8. State machine

| State | Meaning | Motors | Relay | Exits |
| --- | --- | --- | --- | --- |
| `BOOT` | Initialising, outputs forced safe | off | off | to `HOMING` |
| `HOMING` | Seeking home (or calibration) | slow, limited | off | to `SAFE` when done; to `FAULT` on timeout |
| `SAFE` | Default and fail-safe | **off** | off | dashboard ARM after calibration to `ARMED` |
| `ARMED` | Armed, manual mode, jog allowed | on while moving | off | dashboard disarm to `SAFE`; auto mode to `TRACKING` |
| `TRACKING` | Following a target | on while moving | off | target lost to `ARMED`; stable lock and dashboard dead-man held to `LOCKED` |
| `LOCKED` | Marker centred for N frames, dead-man held | on while holding | buzzer pulse only if configured | marker lost or dead-man released to `TRACKING` |
| `FAULT` | Camera lost, throttle, motion error | off | off | dashboard disarm/reset, then to `SAFE` |

Any software e-stop, dashboard disarm, or camera watchdog trip disables motors and the relay. Keep the existing HAT/supply power switch accessible; software cannot cut motor power if the Pi hangs or loses power.

**Lock condition:** target found, `abs(err_px)` within `lock_tolerance_px` on both axes, held for `lock_frames_required` consecutive frames (start at 10 at about 15 FPS).

---

## 9. `config.yaml` (initial)

```yaml
camera:
  device: 0
  width: 640
  height: 480
  fps: 30
  fov_h_deg: 55.0      # approximate, calibrate
  fov_v_deg: 41.0
motors:
  steps_per_rev: 3200  # DIP at 1/16
  pan:  {dir: 13, step: 19, en: 12, min_deg: -45, max_deg: 45, invert: false, max_dps: 90}
  tilt: {dir: 24, step: 18, en: 4,  min_deg: -20, max_deg: 30, invert: false, max_dps: 60}
control:
  kp: 0.12
  ki: 0.0
  kd: 0.01
  deadband_px: 6
  lost_decay_ms: 300
safety:
  deadman_timeout_ms: 300
  home_pan_pin: 23     # not yet fitted
  home_tilt_pin: 25    # not yet fitted
  lock_tolerance_px: 12
  lock_frames_required: 10
  camera_timeout_ms: 500
  jog_timeout_ms: 300
fire:
  relay_pin: 26
  active_low: true     # confirm with the human
  pulse_ms: 300
  cooldown_s: 2.0
detect:
  backend: color       # color | aruco | motion
  color: {h_min: 0, h_max: 10, s_min: 120, v_min: 80, min_area: 400}
  aruco: {dictionary: DICT_4X4_50, id: 7}
server:
  port: 8000
  token: change-me
```

---

## 10. API contract (for `server.py` and the dashboard teammate)

- `GET /video` returns an MJPEG stream (640x480, about 15 FPS).
- `WS /ws/telemetry` sends JSON at about 10 Hz:
  ```json
  {"t": 1764000000.1, "state": "TRACKING",
   "interlocks": {"arm_enabled": true, "deadman": false, "estop": false},
   "pan_deg": 12.4, "tilt_deg": -3.1,
   "target": {"found": true, "x": 322, "y": 240, "w": 80, "h": 120, "err_x": 2, "err_y": -8, "conf": 0.91},
   "lock_frames": 14, "buzzer_pulses": 3,
   "fps": 28.4, "latency_ms": 62, "cpu_temp_c": 58.2, "throttled": false}
  ```
- Commands (header `X-Token` required):

| Request | Body | Notes |
| --- | --- | --- |
| `POST /api/estop` | none | Always accepted; goes to `SAFE` |
| `POST /api/arm` | `{"enabled": true}` | Token-protected; arm requires calibration; false disarms and acknowledges e-stop/fault |
| `POST /api/deadman` | `{"held": true}` | Token-protected hold heartbeat; expires after 300 ms |
| `POST /api/jog` | `{"pan_dps": 20, "tilt_dps": 0}` | Hold-to-move; expires after 300 ms; max 60 deg/s; ignored unless `ARMED` |
| `POST /api/home` | none | Rejected while ARM is on |
| `POST /api/mode` | `{"mode": "manual" or "auto"}` | |
| `GET/PUT /api/config` | tuning values | Range-checked |
| `GET /api/log?limit=100` | none | Recent events |

There is no direct buzzer or e-stop-clear endpoint. The token-protected local dashboard can ARM/disarm and hold the dead-man control.

---

## 11. Test plan

### 11.1 Software only (agent can run, with `--dry-run`)
- PID: step response, anti-windup, deadband, velocity clamp.
- Geometry: pixel to degree conversion at the frame edges and the centre.
- State machine: every transition in section 8, including illegal ones (for example the relay pulse request while in `SAFE` must be refused).
- Watchdogs: jog timeout, camera timeout.

### 11.2 Hardware (human present)
| ID | Test | Pass |
| --- | --- | --- |
| T1 | Motion: sweep each axis, return to zero | back within 0.5 deg |
| T2 | Soft limits | stops at the limit, not beyond |
| T3 | Speed ceiling per axis | no missed steps at the working speed |
| T4 | Homing (once switches fitted), 10 boots | same zero within 1 deg |
| T5 | Capture latency | under 100 ms |
| T6 | Tracking a moving target | no loss for 60 s |
| T7 | Centering error | within 2 deg steady state |
| T8 | Fire gate | buzzer never sounds unless ARM and dead-man and lock are all true; test each false in turn |
| T9 | Kill switch and e-stop | motors and buzzer both dead, with no software involved |
| T10 | Fault handling | unplug camera, throttle flag, limit hit: all go to `SAFE` or `FAULT` |

### 11.3 Performance protocol (adapted from the paper)
Repeat 10 trials per condition: distance 1 m, 2 m, 3 m; light 140 lux and 15 lux; target speed 0.1-1 m/s. Record:
- **Tracking success per direction** (left, right, up, down), as the paper's Table 1. Report the mean of horizontal and vertical.
- **Centred-at-trigger rate:** the percentage of simulated trigger events where the target centre was within tolerance. (This replaces the paper's projectile hit rate.)
- Time to lock, and steady-state error in pixels.

Compare tracking success against the paper's 85-100% range.

---

## 12. Build order

1. Confirm `motion.py` on the bench (`tests/motion_test.py`). Fix issues before anything else.
2. `capture.py` plus `detect.py` (colour backend), tuned to the actual toy target. Print `err_x, err_y`.
3. `control.py` plus unit tests, then a closed loop with real motors on the bench.
4. `safety.py` state machine, dashboard ARM/dead-man, e-stop, watchdogs.
5. `fire.py` optional relay and buzzer, disabled until its module and polarity are confirmed.
6. `server.py` mock-first (same contract as section 10), then the real data.
7. Homing once the limit switches are fitted.
8. Tuning, tests (section 11), README, demo.

---

## 13. Gotchas

- Releasing a GPIO returns it to its default state. GPIO 4 then re-energises motor 2. Always end with `pinctrl set 12,4 op dl`.
- `gpiozero` imports slowly. Create devices once and keep them.
- Python sleeps are not real-time. If step jitter shows up under vision load, move the step generator to a separate process.
- When pasting shell commands for the human, end each block with a newline and keep one command per block (an earlier paste concatenated commands).
- Switch the 12V off whenever wiring or when idle.
- The Pi's SSH address can change. Prefer the hostname.
- Do not leave motors enabled with no load for long. The drivers run warm at about 1.4 A.

---

## Appendix A: `motion.py` reference implementation (untested on hardware)

```python
import math, subprocess, threading, time
from gpiozero import OutputDevice

STEPS_PER_REV = 3200               # 200 x 16 (DIP: S0-S2 and S3-S5 = 0,0,1)
STEPS_PER_DEG = STEPS_PER_REV / 360.0
IDLE_OFF = 2.0                     # seconds idle before the driver is switched off


class Axis:
    """One stepper axis. On this HAT the enable pin is active HIGH."""

    def __init__(self, name, dir_pin, step_pin, en_pin, min_deg, max_deg,
                 invert=False, max_dps=90.0, accel_dps2=400.0):
        self.name = name
        self.dir = OutputDevice(dir_pin, initial_value=False)
        self.step = OutputDevice(step_pin, initial_value=False)
        self.en = OutputDevice(en_pin, initial_value=False)   # low = off
        self.min_steps = int(min_deg * STEPS_PER_DEG)
        self.max_steps = int(max_deg * STEPS_PER_DEG)
        self.invert = invert
        self.max_sps = max_dps * STEPS_PER_DEG
        self.accel = accel_dps2 * STEPS_PER_DEG
        self.pos = 0                       # steps from the start position
        self.target_sps = 0.0
        self.last_move = time.monotonic()
        self._enabled = False
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    @property
    def pos_deg(self):
        return self.pos / STEPS_PER_DEG

    def _set_enabled(self, on):
        self.en.value = 1 if on else 0
        self._enabled = on
        if on:
            time.sleep(0.002)

    def _run(self):
        speed = 0.0
        last = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            dt = min(now - last, 0.05)
            last = now
            tgt = self.target_sps
            eff = tgt if (speed == 0 or tgt * speed > 0) else 0.0   # stop before reversing
            if speed == 0 and eff != 0:
                speed = math.copysign(min(abs(eff), 150.0), eff)    # start speed
            else:
                dv = self.accel * dt
                speed = min(eff, speed + dv) if eff > speed else max(eff, speed - dv)
            if eff == 0 and abs(speed) < 100:
                speed = 0.0
            if speed == 0:
                if self._enabled and now - self.last_move > IDLE_OFF:
                    self._set_enabled(False)
                time.sleep(0.005)
                continue
            direction = 1 if speed > 0 else -1
            nxt = self.pos + direction
            if nxt < self.min_steps or nxt > self.max_steps:        # soft limit
                self.target_sps = 0.0
                speed = 0.0
                continue
            if not self._enabled:
                self._set_enabled(True)
            self.dir.value = 0 if (direction > 0) != self.invert else 1
            half = min(0.5 / abs(speed), 0.01)
            self.step.on(); time.sleep(half)
            self.step.off(); time.sleep(half)
            self.pos = nxt
            self.last_move = time.monotonic()

    def set_velocity_dps(self, dps):
        sps = dps * STEPS_PER_DEG
        self.target_sps = max(-self.max_sps, min(self.max_sps, sps))

    def stop(self):
        self.target_sps = 0.0

    def move_to_deg(self, deg, dps=30.0, timeout=30.0):
        goal = max(self.min_steps, min(self.max_steps, int(round(deg * STEPS_PER_DEG))))
        cap = min(dps * STEPS_PER_DEG, self.max_sps)
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            err = goal - self.pos
            if abs(err) <= 2:
                break
            self.target_sps = math.copysign(min(cap, max(abs(err) * 4.0, 150.0)), err)
            time.sleep(0.005)
        self.target_sps = 0.0
        time.sleep(0.15)

    def close(self):
        self.target_sps = 0.0
        self._stop.set()
        self._t.join(timeout=1)
        self.en.value = 0
        for d in (self.dir, self.step, self.en):
            d.close()
        subprocess.run(["pinctrl", "set", "12,4", "op", "dl"], check=False)
```

Known limitations of the reference code: no homing yet, a single global `pinctrl` call on close, and `move_to_deg` can overshoot by 2-3 steps. Fix these in the real implementation.
