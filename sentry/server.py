from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import hmac
import json
import os
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import config, save_tuning
from .runtime import Runtime


def token_value() -> str:
    return os.getenv("PRAHARI_TOKEN", config["server"]["token"])


def require_token(x_token: str | None = Header(default=None)) -> None:
    if simulation_loopback():
        return
    expected = token_value()
    if not expected or not x_token or not hmac.compare_digest(x_token, expected):
        raise HTTPException(status_code=401, detail="Valid X-Token header required")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config["server"]["host"] in ("0.0.0.0", "::") and \
       token_value() == "change-this-before-lan-access":
        raise RuntimeError("Set PRAHARI_TOKEN before binding the service to the LAN")
    runtime = Runtime()
    app.state.runtime = runtime
    runtime.start()
    try:
        yield
    finally:
        runtime.close()


app = FastAPI(title="PRAHARI", version="1.0.0", lifespan=lifespan)
WEB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
DIST = os.path.join(WEB, "dist")

def simulation_loopback() -> bool:
    return config["runtime"]["simulation"] and config["server"]["host"] in ("127.0.0.1", "localhost", "::1")


class JogCommand(BaseModel):
    pan_dps: float = Field(default=0, ge=-60, le=60)
    tilt_dps: float = Field(default=0, ge=-45, le=45)


class ToggleCommand(BaseModel):
    enabled: bool


class DeadmanCommand(BaseModel):
    held: bool


class ModeCommand(BaseModel):
    mode: str = Field(pattern="^(manual|auto)$")


class ConfigCommand(BaseModel):
    backend: str | None = Field(default=None, pattern="^(color|aruco|motion)$")
    hue_min: int | None = Field(default=None, ge=0, le=179)
    hue_max: int | None = Field(default=None, ge=0, le=179)
    saturation_min: int | None = Field(default=None, ge=0, le=255)
    value_min: int | None = Field(default=None, ge=0, le=255)
    kp: float | None = Field(default=None, ge=0, le=2)
    ki: float | None = Field(default=None, ge=0, le=1)
    kd: float | None = Field(default=None, ge=0, le=1)


@app.get("/")
def dashboard():
    index = os.path.join(DIST, "index.html") if os.path.isfile(os.path.join(DIST, "index.html")) else os.path.join(WEB, "index.html")
    return FileResponse(index)


@app.get("/api/health")
def health():
    rt = app.state.runtime
    return {"status": "ok", "simulation": rt.simulation,
            "camera": rt.camera.status, "state": rt.safety.state.value,
            "home_switches_enabled": config["motors"]["homing_switches_enabled"],
            "buzzer_enabled": config["safety"]["buzzer_enabled"],
            "cpu_temp_c": rt._cpu_temp, "throttled": rt._throttled,
            "throttle_flags_hex": rt._throttle_flags_hex,
            "hardware_interlocks": {"arm": None, "deadman": None,
                                    "source": "physical interlock inputs are not exposed by this backend"}}


@app.get("/api/telemetry", dependencies=[Depends(require_token)])
def telemetry():
    return app.state.runtime.telemetry()


@app.get("/video")
def video(token: str | None = Query(default=None)):
    expected = token_value()
    if not simulation_loopback() and (not token or not hmac.compare_digest(token, expected)):
        raise HTTPException(status_code=401, detail="Valid video token required")
    rt = app.state.runtime
    def frames():
        while True:
            jpeg = rt.jpeg()
            if jpeg is None:
                time.sleep(0.05)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/estop")
def estop():
    app.state.runtime.safety.estop()
    return {"state": "SAFE", "latched": True}


@app.post("/api/arm", dependencies=[Depends(require_token)])
def set_arm(command: ToggleCommand):
    try:
        app.state.runtime.safety.set_arm(command.enabled)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"arm_enabled": command.enabled}


@app.post("/api/deadman", dependencies=[Depends(require_token)])
def set_deadman(command: DeadmanCommand):
    try:
        app.state.runtime.safety.set_deadman(command.held)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"deadman_held": command.held,
            "expires_ms": config["safety"]["deadman_timeout_ms"]}


@app.post("/api/jog", dependencies=[Depends(require_token)])
def jog(command: JogCommand):
    try:
        app.state.runtime.safety.jog(command.pan_dps, command.tilt_dps)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"accepted": True, "expires_ms": config["safety"]["jog_timeout_ms"]}


@app.post("/api/home", dependencies=[Depends(require_token)])
def home():
    try:
        app.state.runtime.safety.home()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"homed": True}


@app.post("/api/calibrate", dependencies=[Depends(require_token)])
def calibrate():
    try:
        app.state.runtime.safety.calibrate()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"calibrated": True, "method": "manual zero"}


@app.post("/api/mode", dependencies=[Depends(require_token)])
def set_mode(command: ModeCommand):
    if command.mode == "auto" and app.state.runtime.detector.backend == "motion" and \
       not app.state.runtime.simulation:
        raise HTTPException(409, "Motion-only detection is restricted to development; use color or ArUco")
    try:
        app.state.runtime.safety.set_mode(command.mode)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"mode": command.mode}


@app.get("/api/config", dependencies=[Depends(require_token)])
def get_config():
    c = config["detect"]["color"]
    p = config["control"]
    return {"backend": app.state.runtime.detector.backend,
            "color": {"hue_min": c["h_min"], "hue_max": c["h_max"],
                      "saturation_min": c["s_min"], "value_min": c["v_min"]},
            "control": {key: p[key] for key in ("kp", "ki", "kd")}}


@app.put("/api/config", dependencies=[Depends(require_token)])
def put_config(command: ConfigCommand):
    rt = app.state.runtime
    values = command.model_dump(exclude_none=True)
    if "backend" in values:
        rt.detector.backend = values.pop("backend")
        config["detect"]["backend"] = rt.detector.backend
    color = config["detect"]["color"]
    mapping = {"hue_min": "h_min", "hue_max": "h_max",
               "saturation_min": "s_min", "value_min": "v_min"}
    for key, dest in mapping.items():
        if key in values:
            color[dest] = values.pop(key)
    for key in ("kp", "ki", "kd"):
        if key in values:
            config["control"][key] = values.pop(key)
    if values:
        raise HTTPException(422, "Unsupported tuning field")
    from .control import Aimer
    rt.safety.aimer = Aimer(config["control"])
    rt.safety.motion.stop()
    save_tuning()
    rt.safety.log.write("config_updated", backend=rt.detector.backend)
    return get_config()


@app.get("/api/log", dependencies=[Depends(require_token)])
def get_log(limit: int = 100):
    return {"events": app.state.runtime.log.recent(limit)}


@app.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket):
    expected = token_value()
    supplied = websocket.query_params.get("token", "")
    if not simulation_loopback() and (not expected or not hmac.compare_digest(supplied, expected)):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    message = {}
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "ts": message.get("ts")})
            except asyncio.TimeoutError:
                pass
            await websocket.send_text(json.dumps(app.state.runtime.telemetry()))
    except WebSocketDisconnect:
        return


ASSETS = os.path.join(DIST, "assets")
if os.path.isdir(ASSETS):
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")
