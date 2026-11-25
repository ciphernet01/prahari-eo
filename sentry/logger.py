from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path


class EventLog:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._recent = deque(maxlen=500)
        self._handler = RotatingFileHandler(self.path, maxBytes=1_000_000,
                                            backupCount=3, encoding="utf-8")
        self._handler.setFormatter(logging.Formatter("%(message)s"))

    def write(self, event: str, **details) -> None:
        row = {"time": time.time(), "event": event, **details}
        encoded = json.dumps(row, separators=(",", ":"), default=str)
        with self._lock:
            self._recent.append(row)
            record = logging.LogRecord("prahari", logging.INFO, "", 0, encoded, (), None)
            self._handler.emit(record)

    def recent(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return list(self._recent)[-max(1, min(500, limit)):]

    def close(self) -> None:
        with self._lock:
            self._handler.close()
