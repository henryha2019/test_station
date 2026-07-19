"""Load + validate the DUT recipe (config/mg996r.json).

The recipe holds everything that varies per product: the functional test profile
(what positions to command) and its per-measurement limit windows. Firmware stays
generic — it reports raw readings; this file is the single source of truth for
what 'good' means.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "mg996r.json"


@dataclass
class Limit:
    """A spec window for one measurement. Any of min/max/expect may be set."""
    min: float | None = None
    max: float | None = None
    expect: str | None = None

    def check(self, value) -> tuple[bool, str]:
        """Return (passed, kind). kind is '', 'low', 'high', or 'mismatch'."""
        if self.expect is not None:
            return (value == self.expect, "" if value == self.expect else "mismatch")
        if self.min is not None and value < self.min:
            return (False, "low")
        if self.max is not None and value > self.max:
            return (False, "high")
        return (True, "")

    def describe(self) -> str:
        if self.expect is not None:
            return f"=={self.expect}"
        lo = "" if self.min is None else f"{self.min:g}"
        hi = "" if self.max is None else f"{self.max:g}"
        return f"[{lo},{hi}]"


@dataclass
class DutConfig:
    dut_id: str
    pwm_us: dict
    settle_ms: int
    limits: dict[str, Limit]
    station: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    # Keys the host checks against limits but are also handy elsewhere.
    @property
    def measured_keys(self) -> list[str]:
        return list(self.limits.keys())

    def validate(self) -> None:
        p = self.pwm_us
        if not (p["min"] < p["center"] < p["max"]):
            raise ValueError("pwm_us must satisfy min < center < max")
        if not self.limits:
            raise ValueError("functional.limits is empty — nothing would be tested")


def load_config(path: str | Path = DEFAULT_CONFIG) -> DutConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    fn = data["functional"]
    limits = {}
    for key, spec in fn["limits"].items():
        if key == "comment":
            continue
        limits[key] = Limit(
            min=spec.get("min"),
            max=spec.get("max"),
            expect=spec.get("expect"),
        )

    cfg = DutConfig(
        dut_id=data["dut_id"],
        pwm_us=fn["pwm_us"],
        settle_ms=int(fn.get("settle_ms", 600)),
        limits=limits,
        station=data.get("station", {}),
        raw=data,
    )
    cfg.validate()
    return cfg
