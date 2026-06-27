"""Station orchestrator — runs one servo end to end and owns the data trail.

Per cycle: command the functional test (the Uno drives the servo and reports
readings), grab a frame, run inference, AND the two verdicts, log a traceable
row, and push the result to the HMI. The orchestrator is the only component that
decides PASS/FAIL.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from . import hmi as hmi_mod
from .camera import Camera
from .config import DutConfig
from .decision import Verdict, decide
from .functional import FunctionalResult, evaluate
from .inspection import Inspector, VisionResult
from .instrument import Instrument
from .tracelog import TraceLog


def _f(meas: dict, key: str):
    v = meas.get(key, "")
    return round(v, 2) if isinstance(v, (int, float)) else v


@dataclass
class UnitRecord:
    timestamp: str
    serial: str
    final_result: str
    fail_reason: str
    functional_result: str
    fail_param: str
    range_deg: object
    center_off_deg: object
    hold_mA: object
    move_mA: object
    speed_dps: object
    direction: object
    test_ms: int
    vision_result: str
    vision_class: str
    vision_conf: float
    infer_ms: float
    cycle_ms: float
    vision_backend: str
    failures: list = field(default_factory=list)

    def to_row(self) -> dict:
        row = asdict(self)
        row.pop("failures", None)
        row["vision_conf"] = round(self.vision_conf, 4)
        row["infer_ms"] = round(self.infer_ms, 2)
        row["cycle_ms"] = round(self.cycle_ms, 2)
        return row


class Station:
    def __init__(
        self,
        cfg: DutConfig,
        instrument: Instrument,
        camera: Camera,
        inspector: Inspector,
        log: TraceLog | None = None,
        hmi: hmi_mod.Hmi | None = None,
    ):
        self.cfg = cfg
        self.instrument = instrument
        self.camera = camera
        self.inspector = inspector
        self.log = log
        self.hmi = hmi or hmi_mod.NullHmi()
        self.tested = 0
        self.passed = 0

    @property
    def fpy(self) -> float:
        """First-pass yield (%). Each unit is tested once, so FPY = pass rate."""
        return 100.0 * self.passed / self.tested if self.tested else 0.0

    def run_unit(self, serial: str) -> UnitRecord:
        t0 = time.perf_counter()

        result = self.instrument.run()
        func: FunctionalResult = evaluate(result.meas, self.cfg, result.elapsed_ms)

        frame = self.camera.capture()
        vis: VisionResult = self.inspector.infer(frame)

        verdict: Verdict = decide(func, vis)
        cycle_ms = (time.perf_counter() - t0) * 1000.0

        self.tested += 1
        if verdict.final_pass:
            self.passed += 1

        m = result.meas
        rec = UnitRecord(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            serial=serial,
            final_result="PASS" if verdict.final_pass else "FAIL",
            fail_reason=verdict.reason,
            functional_result="PASS" if func.passed else "FAIL",
            fail_param=func.fail_param,
            range_deg=_f(m, "range_deg"),
            center_off_deg=_f(m, "center_off_deg"),
            hold_mA=_f(m, "hold_mA"),
            move_mA=_f(m, "move_mA"),
            speed_dps=_f(m, "speed_dps"),
            direction=m.get("direction", ""),
            test_ms=func.elapsed_ms,
            vision_result="PASS" if vis.passed else "FAIL",
            vision_class=vis.cls,
            vision_conf=vis.confidence,
            infer_ms=vis.infer_ms,
            cycle_ms=cycle_ms,
            vision_backend=vis.backend,
            failures=[str(f) for f in func.failures],
        )

        if self.log:
            self.log.append(rec.to_row())
        self.hmi.push(
            hmi_mod.format_frame(serial, func.passed, vis.passed, vis.cls,
                                 verdict.final_pass, self.fpy)
        )
        return rec

    def close(self) -> None:
        for c in (self.instrument, self.camera, self.hmi, self.log):
            try:
                if c and hasattr(c, "close"):
                    c.close()
            except Exception:
                pass
