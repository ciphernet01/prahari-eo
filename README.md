# PRAHARI

PRAHARI is a Raspberry Pi 5 pan/tilt camera prototype for tracking a designated
colour or ArUco marker. It uses the Waveshare Stepper Motor HAT (B), two NEMA 17
motors, OpenCV, a local FastAPI service, and a browser dashboard. An optional relay output is reserved for a 5V buzzer and is disabled by default.
The simple local workflow is IDLE, JOG, or AUTO; selecting JOG/AUTO after
calibration enables camera motion. Manual movement uses WASD, arrow keys, or the
on-screen pad. No projectile, laser, or person-detection model is included.

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

Real hardware mode is the default (`PRAHARI_SIM=0`). It expects the camera and
GPIO hardware to be present; a missing camera is reported as unavailable and
missing GPIO drivers fail startup rather than silently substituting simulated
data. For UI or logic development without hardware, simulation must be
explicitly enabled:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
$env:PRAHARI_SIM = "1"
py -m sentry.launch
```

Open `http://127.0.0.1:8000`. Simulation uses a generated moving marker and
does not open GPIO. To use a local webcam while keeping motors simulated, set
`$env:PRAHARI_CAMERA_SIM = "0"` as well. Never enable simulation for a real
hardware run.

## Raspberry Pi 5 deployment

Use 64-bit Raspberry Pi OS Trixie, following the verified setup in the build
spec. Install system packages so OpenCV and GPIO libraries match the Pi OS:

```bash
sudo apt update
sudo apt install -y python3-venv python3-opencv python3-numpy python3-lgpio \
  python3-gpiozero python3-yaml v4l-utils git
cd ~/prahari-eo
if [ ! -x ~/prahari-env/bin/python ]; then python3 -m venv --system-site-packages ~/prahari-env; fi
source ~/prahari-env/bin/activate
python -m pip install 'fastapi>=0.115,<1' 'uvicorn[standard]>=0.30,<1'
```

For software-only checks, simulation is opt-in:

```bash
PRAHARI_SIM=1 PRAHARI_CAMERA_SIM=0 ~/prahari-env/bin/python -m sentry.launch
```

For actual hardware, after the frame and travel stops are built and checked,
run with the default hardware mode (`PRAHARI_SIM=0`). The dashboard and API need no token while bound to
loopback (`127.0.0.1`). To use a second device on trusted Wi-Fi, set a strong
`PRAHARI_TOKEN` and `PRAHARI_HOST=0.0.0.0`; never
forward the service port to the public internet. For a service install, run
`bash scripts/install_pi.sh` from `~/prahari-eo`, create `/etc/prahari.env` with
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

1. Secure the camera pan/tilt assembly and confirm the configured soft limits
   match the safe mechanical travel. Keep the motor power switch accessible.
2. Keep the buzzer relay disabled while the buzzer is disconnected.
3. Start with `PRAHARI_SIM=0` for real motors and the real camera. On the local
   Pi, the service binds to `127.0.0.1`; no API token is required on loopback.
4. With the axes centered and stationary, use **Set Current Zero** twice to
   confirm calibration. Select **JOG** and use short WASD/arrow-pad movements.
   Select **AUTO** for red/ArUco marker or motion tracking; select **IDLE** to
   stop and disable motor movement.
5. Test target loss, the E-STOP, camera disconnect, and the physical motor-power
   cut before leaving a bench setup unattended.

The E-STOP is latched; restarting the service clears it after the cause has been
checked. The separate physical power cut is required because software cannot
stop a driver if the Pi loses power. Keep the service on loopback unless you set
a strong `PRAHARI_TOKEN` before binding it to a trusted LAN.
## Service surface

- `GET /api/health`, `GET /api/telemetry`, `WS /ws/telemetry`
- `GET /video` (MJPEG)
- `POST /api/jog` (hold-to-move velocity; expires after 300 ms)
- `POST /api/arm` and `POST /api/deadman` (legacy routes; not called by dashboard)
- `POST /api/home`, `POST /api/calibrate`, `POST /api/mode`
- `POST /api/estop` (always accepted; no token needed)
- `GET/PUT /api/config` for detector thresholds and PID gains
- `GET /api/log`

The dashboard has no ARM, dead-man, or direct buzzer buttons. JOG/AUTO mode
selection enables motion after zero calibration; IDLE stops it. Buzzer output
remains disabled unless explicitly configured. Detector choices are `color`,
`aruco`, and `motion` (simple frame-difference motion detection).

## Software checks

```bash
python -m pytest
```

These cover pure geometry/control and detector logic. Hardware checks are
manual and must be run with a person present at the motor power switch; no
hardware tests are run by this repository's test suite.
