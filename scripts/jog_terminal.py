#!/usr/bin/env python3
"""WASD terminal jog client for the PRAHARI local FastAPI service.

Run on the Raspberry Pi while sentry.launch is running. This script does not
drive GPIO directly; all movement is sent to /api/jog and uses backend limits.
"""
from __future__ import annotations

import argparse
import json
import os
import select
import sys
import termios
import time
import tty
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


POLL_S = 0.025
SEND_S = 0.100
KEY_HOLD_S = 0.250  # terminal has no key-up events; stay under the 300 ms API watchdog
KEYS = {"w": "up", "a": "left", "s": "down", "d": "right"}


class Api:
    def __init__(self, base: str, token: str = "") -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["X-Token"] = self.token
        req = Request(self.base + path, data=data, headers=headers,
                      method="GET" if data is None else "POST")
        try:
            with urlopen(req, timeout=2) as response:
                return json.loads(response.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"API {exc.code}: {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Cannot reach PRAHARI at {self.base}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Use WASD key repeat to jog PRAHARI pan/tilt")
    parser.add_argument("--url", default=os.getenv("PRAHARI_URL", "http://127.0.0.1:8000"),
                        help="PRAHARI base URL (default: %(default)s)")
    parser.add_argument("--speed", type=float, default=12.0,
                        help="Jog speed in degrees/second (default: %(default)s)")
    args = parser.parse_args()
    if not 0 < args.speed <= 60:
        parser.error("--speed must be greater than 0 and no more than 60 deg/s")
    if not sys.stdin.isatty():
        print("Run this script directly in a terminal so it can read WASD keys.", file=sys.stderr)
        return 2

    api = Api(args.url, os.getenv("PRAHARI_TOKEN", ""))
    try:
        health = api.call("/api/health")
        if health.get("simulation"):
            raise RuntimeError("Backend is in SIM mode; start it with PRAHARI_SIM=0 on the Pi.")
        camera_deadline = time.monotonic() + 10
        while not health.get("camera", {}).get("available") and time.monotonic() < camera_deadline:
            time.sleep(0.5)
            health = api.call("/api/health")
        if "throttle_active_flags_hex" not in health:
            raise RuntimeError("Backend is outdated; pull the latest main branch and restart PRAHARI.")
        active_flags = int(health.get("throttle_active_flags_hex") or "0", 16)
        if health.get("throttled") or active_flags:
            flags = health.get("throttle_active_flags_hex") or "non-zero"
            raise RuntimeError(f"Pi reports active throttling/undervoltage ({flags}); motion locked out.")
        voltage = health.get("pi_5v_v")
        if voltage is not None and voltage < 4.8:
            raise RuntimeError(f"Pi 5 V input is low ({voltage:.3f} V); motion locked out.")
        if not health.get("camera", {}).get("available"):
            detail = health.get("camera", {}).get("error") or "no fresh frames received"
            raise RuntimeError(f"Camera is not available ({detail}); check /dev/video0 and retry.")
        state = api.call("/api/telemetry")
        if state.get("fault") or state.get("state") == "FAULT":
            raise RuntimeError(f"Backend fault is active: {state.get('fault') or 'inspect dashboard'}")
        if state.get("interlocks", {}).get("estop"):
            raise RuntimeError("E-STOP is latched. Resolve the cause and restart the service to clear it.")
        axes = state.get("axes", {})
        if not (axes.get("pan", {}).get("calibrated") and
                axes.get("tilt", {}).get("calibrated")):
            print("Both axes need a zero reference. Center them mechanically first.")
            if input("Set the current position as zero? Type YES to confirm: ").strip() != "YES":
                print("Cancelled; no motion command sent.")
                return 0
            api.call("/api/calibrate", {})
        api.call("/api/mode", {"mode": "manual"})
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"PRAHARI jog unavailable: {exc}", file=sys.stderr)
        return 1

    print("PRAHARI terminal jog | W/S = tilt | A/D = pan | Q or Ctrl-C = stop/exit")
    print(f"Speed: {args.speed:g} deg/s. Tap for a nudge; hold to repeat. Release to stop.")
    print("Keep the mechanism clear and the physical motor power switch reachable.")

    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    last_key: dict[str, float] = {}
    last_send = 0.0
    last_command = (0.0, 0.0)
    quitting = False

    def command() -> tuple[float, float]:
        now = time.monotonic()
        active = {key for key, stamp in last_key.items() if now - stamp <= KEY_HOLD_S}
        pan = args.speed * (int("d" in active) - int("a" in active))
        tilt = args.speed * (int("w" in active) - int("s" in active))
        return pan, tilt

    try:
        tty.setraw(fd)
        while not quitting:
            ready, _, _ = select.select([sys.stdin], [], [], POLL_S)
            if ready:
                key = os.read(fd, 1).decode(errors="ignore").lower()
                if key in ("q", "\x03"):
                    quitting = True
                    continue
                if key in KEYS:
                    last_key[key] = time.monotonic()
                    # Send the initial tap immediately; terminal key repeat may
                    # have a longer initial delay than the backend watchdog.
                    last_send = 0.0

            now = time.monotonic()
            desired = command()
            if now - last_send >= SEND_S and (desired != (0.0, 0.0) or last_command != (0.0, 0.0)):
                api.call("/api/jog", {"pan_dps": desired[0], "tilt_dps": desired[1]})
                last_command = desired
                last_send = now
    except KeyboardInterrupt:
        pass
    except (RuntimeError, OSError) as exc:
        print(f"\nJog stopped: {exc}", file=sys.stderr)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        try:
            api.call("/api/jog", {"pan_dps": 0, "tilt_dps": 0})
            api.call("/api/mode", {"mode": "idle"})
        except (RuntimeError, OSError):
            # The backend's 300 ms jog watchdog remains the fallback stop.
            pass
        print("\nJog stopped; PRAHARI set to IDLE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
