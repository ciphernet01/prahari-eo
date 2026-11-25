# Bench-control notes

The current build uses the local dashboard's IDLE/JOG/AUTO modes; no separate
ARM or dead-man GPIO switches are part of this bench setup. Keep the physical
motor-power switch accessible, verify soft limits against the frame, and leave
the optional buzzer disconnected/disabled until it is wired and checked.

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

For the Pi 5, use an independent official 27 W USB-C supply for the Pi and the
regulated 12 V / 5 A supply for the HAT/motors. With all power off, set the
HAT's Pi-power switch OFF before connecting USB-C. Waveshare describes this
switch as controlling power to the Raspberry Pi; motor VM comes from the HAT's
DC input. Never connect USB-C while the HAT switch is ON, as that joins two 5 V
sources. [Waveshare HAT B wiki](https://www.waveshare.com/wiki/Stepper_Motor_HAT_%28B))

The earlier bench arrangement powered the Pi through the HAT's 5 V regulator
(rated up to 3 A) and measured **4.77978 V**, with `get_throttled=0x50000`.
The Pi 5 is recommended to use Raspberry Pi's 27 W USB-C supply. After a power
change, reboot and confirm `vcgencmd get_throttled` returns `0x0` and
`vcgencmd pmic_read_adc EXT5V_V` is above 4.8 V before enabling movement.
[Raspberry Pi power guidance](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)

## 4. Software controls, home switches, and optional buzzer

Use IDLE/JOG/AUTO in the dashboard; there are no ARM or dead-man GPIO switches
in this build. The dashboard has no buzzer button. The terminal jog client uses
Enter to request one configured short buzzer cue from the backend.

| Function | BCM GPIO | Wiring / behavior |
|---|---:|---|
| Pan home switch | 23 | Normally open to GND; closed at negative pan travel end |
| Tilt home switch | 25 | Normally open to GND; closed at negative tilt travel end |
| Optional buzzer relay input | 26 | BCM 26 is physical header pin 37; connect to relay IN1 only after checking that the module input accepts 3.3 V logic |

For a single-channel use on a 4-channel relay board, use channel 1 contacts:
external 5 V buzzer supply `+` to `COM1`, `NO1` to active buzzer `+`, and
buzzer `−` to that supply's `−`. `NO1` keeps the buzzer off when the relay is
idle. The relay input side uses Pi GPIO 26, Pi GND, and the relay board's rated
logic supply as marked on its silkscreen/manual. Do not guess the board's
`VCC`/`JD-VCC` jumper wiring, input polarity, or 3.3 V compatibility; confirm
the exact module first. Never connect relay contacts to GPIO or feed the
buzzer's external 5 V into a Pi GPIO pin.

Keep `safety.buzzer_enabled: false` until wiring and relay polarity are
verified. Then enable it and set `safety.relay_active_low` to match the
module's input. `safety.buzzer_pulse_ms` controls beep length and
`safety.buzzer_cooldown_s` sets the minimum interval between cues.

Home switches are optional; without them, center the axes manually and use the
dashboard's **Set current position as zero** action after each reboot. Fit
physical stops for both ends of both axes. Software limits do not replace
mechanical stops. The dashboard e-stop cannot protect against a crashed or
unpowered Pi, so keep the existing HAT/supply motor-power switch accessible.
The current software travel window, relative to the confirmed zero, is pan
−60° to +60° and tilt −35° to +45°. Confirm the assembled frame and cable slack
can safely cover that travel before jogging to the limits.
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
3. With the frame clear and 12 V switch accessible, set `PRAHARI_SIM=0`. Leave
   the dashboard in IDLE. Jog is unavailable until both axes are calibrated.
4. Center the camera manually, then use **Set current position as zero**. The
   system's software limits are relative to that point. If home switches are
   fitted and `homing_switches_enabled: true` is set in `config.yaml`, home at
   the negative travel switches instead; each switch must be placed at its
   configured negative limit.
5. Select JOG and use short, slow manual jogs. Verify each arrow,
   release timeout, soft limit, and physical stop separately before attaching
   any moving accessories.
6. Keep buzzer output disabled until the relay board pinout and input polarity
   are confirmed, then test one short cue with the buzzer mechanism clear.

The app currently assumes direct drive. Edit `config.yaml` angle limits and
axis direction after measuring the completed frame. Homing, camera field of
view, color thresholds, and PID values must be tuned on the actual assembly.
