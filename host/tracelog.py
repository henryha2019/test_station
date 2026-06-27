"""Per-unit traceability log (one CSV row per tested servo).

Includes the key analog measurements (angle range, currents, speed) so downstream
analysis can do not just FPY/Pareto but parametric studies (Cpk, Gage R&R) on the
continuous readings. Keyed by serial number. Header is fixed; new runs append.
"""
from __future__ import annotations

import csv
from pathlib import Path

FIELDS = [
    "timestamp",
    "serial",
    "final_result",       # PASS / FAIL
    "fail_reason",        # -, FUNCTIONAL, VISION, FUNCTIONAL+VISION
    "functional_result",  # PASS / FAIL
    "fail_param",         # failing measurement name or -
    "range_deg",          # measured travel
    "center_off_deg",     # center error
    "hold_mA",            # holding current at center
    "move_mA",            # peak current during sweep
    "speed_dps",          # travel speed
    "direction",          # increasing / decreasing
    "test_ms",            # functional test time
    "vision_result",      # PASS / FAIL
    "vision_class",       # predicted class
    "vision_conf",        # P(predicted class)
    "infer_ms",           # inference latency
    "cycle_ms",           # total host cycle time
    "vision_backend",     # baseline / tflite-int8
]


class TraceLog:
    def __init__(self, path: str | Path = "logs/log.csv"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.path.exists() or self.path.stat().st_size == 0
        self._fh = self.path.open("a", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._fh, fieldnames=FIELDS)
        if new:
            self._w.writeheader()
            self._fh.flush()

    def append(self, record: dict) -> None:
        self._w.writerow({k: record.get(k, "") for k in FIELDS})
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
