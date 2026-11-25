from fastapi.testclient import TestClient

from sentry.config import config
from sentry.server import app, token_value


def test_simulated_app_startup_and_authenticated_dashboard_api(monkeypatch):
    monkeypatch.setitem(config["runtime"], "simulation", True)
    monkeypatch.setitem(config["server"], "host", "0.0.0.0")
    monkeypatch.setenv("PRAHARI_TOKEN", "test-token")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        health = client.get("/api/health").json()
        assert health["simulation"] is True
        assert health["camera"]["simulation"] is True
        assert client.get("/api/telemetry").status_code == 401
        headers = {"X-Token": token_value()}
        assert client.get("/api/telemetry", headers=headers).status_code == 200
        assert client.post("/api/jog", headers=headers,
                           json={"pan_dps": 10, "tilt_dps": 0}).status_code == 409
        assert client.post("/api/arm", headers=headers,
                           json={"enabled": True}).status_code == 409
        assert client.post("/api/calibrate", headers=headers).status_code == 200
        assert client.post("/api/arm", headers=headers,
                           json={"enabled": True}).status_code == 200
        assert client.post("/api/deadman", headers=headers,
                           json={"held": True}).status_code == 200
        assert client.post("/api/estop").status_code == 200
        assert client.post("/api/arm", headers=headers,
                           json={"enabled": False}).status_code == 200
        paths = app.openapi()["paths"]
        assert "/api/arm" in paths
        assert "/api/fire" not in paths
