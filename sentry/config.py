"""Small YAML configuration loader with conservative defaults."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.getenv("PRAHARI_CONFIG", ROOT / "config.yaml"))


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    server = config.setdefault("server", {})
    server["host"] = os.getenv("PRAHARI_HOST", server.get("host", "127.0.0.1"))
    server["port"] = int(os.getenv("PRAHARI_PORT", server.get("port", 8000)))
    server["token"] = os.getenv("PRAHARI_TOKEN", server.get("token", ""))
    return config


def save_tuning() -> None:
    """Persist only the API-editable detector and PID tuning values."""
    import tempfile

    with CONFIG_PATH.open("r", encoding="utf-8") as stream:
        saved = yaml.safe_load(stream) or {}
    saved.setdefault("detect", {})["backend"] = config["detect"]["backend"]
    saved["detect"]["color"] = config["detect"]["color"]
    saved["control"] = config["control"]
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_PATH.parent,
                                     delete=False, suffix=".tmp") as stream:
        yaml.safe_dump(saved, stream, sort_keys=False)
        temp_path = Path(stream.name)
    temp_path.replace(CONFIG_PATH)


config = load_config()


def camera_config() -> dict: return config["camera"]
def motor_config() -> dict: return config["motors"]
def safety_config() -> dict: return config["safety"]
def detector_config() -> dict: return config["detect"]
