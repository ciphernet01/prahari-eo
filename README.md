# PRAHARI

PRAHARI is a Raspberry Pi 5 pan/tilt camera prototype for tracking a designated
colour or ArUco marker. It uses the Waveshare Stepper Motor HAT (B), two NEMA 17
motors, OpenCV, a local FastAPI service, and a browser dashboard. An optional relay output is reserved for a buzzer and is disabled by default.
There is no projectile, laser, or person-detection model. The EO-C2 dashboard
has no ARM, dead-man, or direct buzzer controls. The latest interface requires
physical ARM/dead-man interlocks, but this backend does not yet read or enforce
them; the dashboard reports those inputs unavailable and inhibits motion.

This repository can be developed on Windows and copied to the Pi. The Pi is the
hardware host for the finished system. Simulation is a development mode only.

## State of the hardware integration

The HAT and both motors passed the bench tests documented in `sitrep.txt`. The
motor map, active-high enable polarity, 1/16 DIP setting, and supply arrangement
are in [docs/wiring.md](docs/wiring.md). The frame and limit switches are not
yet fitted according to the build spec. Until the assembled frame is checked,
use simulation or keep the motors detached from it. GPIO jogging is bounded by
configured software limits but cannot replace physical stops or homing.

## Dashboard build

The offline React/Vite dashboard is served from `web/dist`. Build it once on a development machine; Node is not required at runtime on the Pi.

```powershell
cd web
npm ci
npm run build
cd ..
```

For frontend development, keep FastAPI running in another terminal, then run `cd web; npm run dev`. Vite proxies `/api`, `/video`, and `/ws` to `127.0.0.1:8000`.

## Windows development

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
$env:PRAHARI_SIM = "1"
py -m sentry.launch
```

Open `http://127.0.0.1:8000`. By default, simulation uses a moving red
marker and opens no GPIO. To use a local webcam while keeping the motors in
simulation, set `$env:PRAHARI_SIM = "1"` and `$env:PRAHARI_CAMERA_SIM = "0"`
before launch. The dashboard/API is for integration development and does not
replace physical bring-up and tuning on the Pi.

## Raspberry Pi 5 deployment

Use 64-bit Raspberry Pi OS Trixie, following the verified setup in the build
spec. Install system packages so OpenCV and GPIO libraries match the Pi OS:

```bash
sudo apt update
sudo apt install -y python3-venv python3-opencv python3-numpy python3-lgpio \
  python3-gpiozero python3-yaml v4l-utils git
cd ~/turret
if [ ! -x ~/turret-env/bin/python ]; then python3 -m venv --system-site-packages ~/turret-env; fi
source ~/turret-env/bin/activate
python -m pip install 'fastapi>=0.115,<1' 'uvicorn[standard]>=0.30,<1'
```

Run **dry-run first**:

```bash
PRAHARI_SIM=1 ~/turret-env/bin/python -m sentry.launch
```

For actual hardware, after the frame and travel stops are built and checked,
run with `PRAHARI_SIM=0`. On real hardware, the local dashboard needs
the token configured in `config.yaml` or `PRAHARI_TOKEN`. To use a second device
on the trusted Wi-Fi, set a strong token and `PRAHARI_HOST=0.0.0.0`; never
forward the service port to the public internet. For a service install, run
`bash scripts/install_pi.sh` from `~/turret`, create `/etc/prahari.env` with
your chosen `PRAHARI_SIM`, `PRAHARI_HOST`, and `PRAHARI_TOKEN`, review the unit,
then enable it:

```bash
sudo systemctl enable --now prahari
```

On this verified setup, the HAT powers the Pi from its regulator: HAT switch ON,
12 V supply connected, Pi USB-C unplugged. Do not connect the Pi USB-C while
that switch is ON. Watch `vcgencmd get_throttled` during camera and motor load;
the runtime reports non-zero flags as a fault.

## First real-hardware sequence

1. Fit the frame and physical travel stops. Do not operate motors until the
   physical ARM and dead-man switches are wired to documented GPIO inputs and
   their state is enforced by the backend. The current repo has no pin mapping
   or input implementation; do not guess switch pins. Home switches are optional
   for zero calibration but required for the Home Axes command.
2. Leave the buzzer relay disabled until its model and active polarity are
   verified. The dashboard has no direct buzzer trigger endpoint.
3. Start `PRAHARI_SIM=0` with the frame clear and an accessible 12 V switch.
4. Center both axes and use **Set current position as zero** while the system is
   safe. Motion controls remain inhibited until physical interlock telemetry and
   enforcement are implemented in the backend.
5. Tune the color detector for a dedicated red marker (or select an ArUco
   marker through the API), then tune PID on a stationary, non-human target.
6. Test target loss, e-stop, camera disconnect, and the physical motor-power
   cut before operating with the frame assembled.

The software e-stop is latched by the E-STOP endpoint. The separate physical
power cut is required because software cannot stop a driver after the Pi loses
power. The current backend still contains legacy software ARM/dead-man routes,
but the EO-C2 dashboard does not call them. Physical switch GPIO mappings and
backend enforcement are outstanding integration work. This remains a local
marker-tracking prototype, not a remote threat-response system.

## Service surface

- `GET /api/health`, `GET /api/telemetry`, `WS /ws/telemetry`
- `GET /video` (MJPEG)
- `POST /api/jog` (hold-to-move velocity; expires after 300 ms)
- `POST /api/arm` and `POST /api/deadman` (legacy API routes; not called by EO-C2 UI)
- `POST /api/home`, `POST /api/calibrate`, `POST /api/mode`
- `POST /api/estop` (always accepted; no token needed)
- `GET/PUT /api/config` for detector thresholds and PID gains
- `GET /api/log`

The browser dashboard does not expose ARM, dead-man, or direct buzzer controls. The service currently does not report physical ARM/dead-man switch inputs; the EO-C2 UI marks those inputs unavailable and inhibits motor jog/auto until the backend reports them. The `/api/arm` and `/api/deadman` routes remain in this legacy backend and are not called by the dashboard. There is no endpoint to directly switch the buzzer or bypass its lock check.
The buzzer is disabled by default. The current backend lock cue still depends
on its legacy software ARM/dead-man state and stable marker lock; that logic must
be updated to use physical interlock inputs before hardware operation. The detector backends are `color` (default), `aruco`, and
development-only `motion`. They detect a designated marker, not a person or
animal.

## Software checks

```bash
python -m pytest
```

These cover pure geometry/control and detector logic. Hardware checks are
manual and must be run with a person present at the motor power switch; no
hardware tests are run by this repository's test suite.
