from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    x: float
    y: float
    w: float
    h: float
    confidence: float = 1.0

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h,
                "conf": self.confidence}
