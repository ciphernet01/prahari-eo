from enum import Enum

from fastapi.testclient import TestClient

from sentry.config import config
from sentry.server import app, token_value


class RuntimeState(str, Enum):
    SAFE = "SAFE"


class RuntimeStub:
    def __init__(self):
        self.camera = type(
            "CameraStub",
            (),
            {"status": {"available": True, "age_ms": 10, "error": None}},
        )()
        self.safety = type("SafetyStub", (), {"state": RuntimeState.SAFE})()
        self.detector = type("DetectorStub", (), {"backend": "color"})()
        self._cpu_temp = None
        self._throttled = False
        self._throttle_flags_hex = None

    def start(self):
        pass

    def close(self):
        pass

    def telemetry(self):
        return {"state": "SAFE", "axes": {}, "target": None}


def test_hardware_api_authentication_and_health(monkeypatch):
    monkeypatch.setattr("sentry.server.Runtime", RuntimeStub)
    monkeypatch.setitem(config["server"], "host", "0.0.0.0")
    monkeypatch.setenv("PRAHARI_TOKEN", "test-token")

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["camera"]["available"] is True
        assert "simulation" not in health.json()

        assert client.get("/api/telemetry").status_code == 401
        headers = {"X-Token": token_value()}
        assert client.get("/api/telemetry", headers=headers).status_code == 200
