# Wiring guide status

> **Interlock integration gap:** The current guide below documents the earlier software ARM/dead-man arrangement. The latest EO-C2 requirement is for physical ARM and dead-man switches. This repository does not assign GPIO pins for these switches or read them in the backend. Do not assume the dashboard can enable motion: it will show the inputs as unavailable and inhibit jog/auto. Define, wire, and implement both physical inputs before hardware motion bring-up; do not guess pins.

# PRAHARI wiring and Pi bring-up

This procedure follows the bench-verified setup in `sitrep.txt` and
`PRAHARI_AGENT_BUILD_SPEC.md`. Check your actual HAT silk screen and revision
against the [Waveshare Stepper Motor HAT (B) wiki](https://www.waveshare.com/wiki/Stepper_Motor_HAT_%28B%29).

## 1. Motor HAT and motors

Disconnect 12 V and shut down the Pi before wiring. Seat the HAT directly on
the Pi 40-pin header. The motor connectors are the HAT output terminals; do not
connect a motor coil to GPIO pins.

| Axis | HAT outputs | Motor lead colors | HAT control pins (BCM DIR / STEP / ENABLE) |
|---|---|---|---|
| Pan, channel 1 | A1, A2, B1, B2 | A1 black, B1 red, A2 green, B2 blue | 13 / 19 / 12 |
| Tilt, channel 2 | A3, A4, B3, B4 | A3 black, B3 red, A4 green, B4 blue | 24 / 18 / 4 |

Coils are black/green and red/blue. The tested enable on this exact setup is
active high: high enables the driver; low disables it. GPIO 4 has a pull-up at
Pi boot, so startup must drive BCM 12 and 4 low before any movement. The
software does this with `pinctrl`; the boot configuration notes below cover the
interval before the service starts.

## 2. HAT switches and motor current

With 12 V off, set hardware microstepping to 1/16: S0/S1/S2 = 0/0/1 and
S3/S4/S5 = 0/0/1 (0 at top, 1 at bottom per the board silk screen). The six
mode GPIO pins are intentionally unused. The tested setting gives 3,200 steps
per revolution (200 full steps × 16). Keep the present potentiometer setting;
do not change it until Vref and motor current are checked. The build report
records approximately 1.4 A from Vref, with a target around 1.1 V for these
motors.

## 3. Power

The tested bench setup is exact and must be preserved until we verify a
different supply arrangement: regulated 12 V / 5 A into the HAT DC jack, HAT
power switch ON, Pi USB-C unplugged. The HAT regulator then supplies the Pi.
Never plug Pi USB-C in while the HAT switch is ON; that supply combination has
not been tested. Turn 12 V off before connecting or changing motor wiring.

The HAT input is 8.2–28 V. Its 5 V regulator is rated up to 3 A, while Pi 5
documentation recommends a 5 V / 5 A supply for full USB peripheral power.
That makes runtime undervoltage monitoring important with the webcam attached.
If `vcgencmd get_throttled` reports non-zero flags during camera/motor load,
stop and resolve power issues before increasing speed or load. See [Raspberry
Pi's Pi 5 power guidance](https://www.raspberrypi.com/documentation/computers/getting-started.html?m=p).

## 4. Dashboard controls and optional home switches

ARM and dead-man are dashboard controls in this version. Do not add GPIO5/6
switch wiring. ARM starts disarmed and authorizes software motion after axis
calibration. The dashboard dead-man only gates the optional buzzer indication;
it does not control motor movement. Both controls require the configured API
token.

| Function | BCM GPIO | Wiring / behavior |
|---|---:|---|
| Pan home switch | 23 | Normally open to GND; closed at negative pan travel end |
| Tilt home switch | 25 | Normally open to GND; closed at negative tilt travel end |
| Optional buzzer relay input | 26 | Leave disconnected and software-disabled until relay polarity is verified |

Home switches are optional; without them, center the axes manually and use the
dashboard's **Set current position as zero** action after each reboot. Fit
physical stops for both ends of both axes. Software limits do not replace
mechanical stops. The dashboard e-stop cannot protect against a crashed or
unpowered Pi, so keep the existing HAT/supply motor-power switch accessible.
This remains a local marker-tracking prototype, not a field-rated remote
interlock or threat-response system.

## 5. Pi boot-safe GPIO

Because BCM 4 can pull high during boot on this setup, add these lines to
`/boot/firmware/config.txt` before operating the HAT from an unattended boot:

```ini
gpio=12=op,dl
gpio=4=op,dl
```

Reboot with the HAT motor supply disconnected first and confirm the Pi boots.
At application start and exit the service also runs:

```bash
pinctrl set 12,4 op dl
```

Do not set these to `dh`; high enables the tested drivers.

## 6. First motion procedure

1. Finish the frame, mount physical stops, and test that it moves freely by
   hand while driver power is off.
2. Start with `PRAHARI_SIM=1` to verify the dashboard and API. Dry-run uses a
   synthetic red marker and does not claim any GPIO.
3. With the frame clear and 12 V switch accessible, set `PRAHARI_SIM=0`. Keep
   dashboard ARM off. Jog is rejected until both axes are calibrated.
4. Center the camera manually, then use **Set current position as zero**. The
   system's software limits are relative to that point. If home switches are
   fitted and `homing_switches_enabled: true` is set in `config.yaml`, home at
   the negative travel switches instead; each switch must be placed at its
   configured negative limit.
5. Turn dashboard ARM on and use short, slow manual jogs. Verify each arrow,
   release timeout, soft limit, and physical stop separately before attaching
   any moving accessories.
6. Keep buzzer output disabled until its relay model, active polarity, and
   series ARM wiring are verified.

The app currently assumes direct drive. Edit `config.yaml` angle limits and
axis direction after measuring the completed frame. Homing, camera field of
view, color thresholds, and PID values must be tuned on the actual assembly.
