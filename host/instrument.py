"""Functional instrument transport (the servo test instrument).

`Instrument` is the interface the orchestrator depends on. Two backends:
  * SerialInstrument — talks to the board over USB serial (pyserial). The board
    commands the servo and reports AS5600 angle + INA219 current readings.
  * SimInstrument    — synthesizes the SAME wire protocol from a fault scenario,
    so the whole station runs with no hardware. It emits real MEAS/DONE text and
    parses it back, exercising protocol.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import protocol
from .config import DutConfig


@dataclass
class MeasResult:
    meas: dict          # measurement key -> value (float or str)
    elapsed_ms: int


class Instrument:
    def identify(self) -> protocol.IdInfo:  # pragma: no cover - interface
        raise NotImplementedError

    def run(self) -> MeasResult:            # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# --------------------------------------------------------------------------- #
# Real hardware
# --------------------------------------------------------------------------- #
class SerialInstrument(Instrument):
    def __init__(self, port: str, baud: int = 115200, timeout: float = 6.0):
        import serial  # local import so the sim path needs no pyserial
        import time
        self._ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2.0)  # the board auto-resets on port open; wait for boot
        self._ser.reset_input_buffer()

    def _cmd(self, cmd: str) -> None:
        self._ser.write((cmd + "\n").encode("ascii"))
        self._ser.flush()

    def send_line(self, s: str) -> None:
        """Write a raw line (used by SharedSerialHmi to push the OLED frame over
        this same link on the single-board ESP32-CAM)."""
        self._ser.write((s + "\n").encode("ascii"))
        self._ser.flush()

    def _readline(self) -> str:
        return self._ser.readline().decode("ascii", "replace").strip()

    def identify(self) -> protocol.IdInfo:
        self._cmd(protocol.CMD_ID)
        return protocol.parse_id(self._readline())

    def run(self) -> MeasResult:
        self._cmd(protocol.CMD_RUN)
        meas: dict = {}
        elapsed = 0
        while True:
            line = self._readline()
            if not line:
                raise TimeoutError("no response from instrument during test")
            if line.startswith("MEAS,"):
                key, value = protocol.parse_meas(line)
                meas[key] = value
            elif line.startswith("DONE,"):
                elapsed = protocol.parse_done(line)
                break
            elif line.startswith("ERR,"):
                raise RuntimeError(f"instrument error: {line}")
        return MeasResult(meas=meas, elapsed_ms=elapsed)

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
# Nominal readings for a healthy MG996R (rough, illustrative values). This unit
# is the extended-travel variant (~180 degrees each way from center), hence
# range_deg ~300 rather than the ~120 of a standard hobby servo -- keep this in
# sync with config/mg996r.json's range_deg window (also a placeholder pending
# calibration against the real hardware).
_NOMINAL = {
    "idle_mA": 8.0,
    "hold_mA": 25.0,
    "move_mA": 350.0,
    "range_deg": 300.0,
    "center_off_deg": 3.0,
    "speed_dps": 400.0,
}

SCENARIOS = ["good", "no_response", "stalled", "reversed", "out_of_range", "slow", "offcenter"]


def build_meas(cfg: DutConfig, scenario: str, rng: np.random.Generator) -> dict:
    """Synthesize a measurement dict for a fault scenario (with realistic noise)."""
    m = {k: float(v + rng.normal(0, abs(v) * 0.04 + 0.5)) for k, v in _NOMINAL.items()}
    m["center_off_deg"] = abs(m["center_off_deg"])
    direction = "increasing"

    if scenario == "good":
        pass
    elif scenario == "no_response":            # dead signal / no motion
        m["range_deg"] = float(rng.uniform(0, 3))
        m["speed_dps"] = float(rng.uniform(0, 10))
        m["move_mA"] = float(rng.uniform(5, 25))
        m["hold_mA"] = float(rng.uniform(2, 10))
    elif scenario == "stalled":                # jammed gearbox -> overcurrent
        m["range_deg"] = float(rng.uniform(2, 15))
        m["move_mA"] = float(rng.uniform(1100, 1600))
        m["hold_mA"] = float(rng.uniform(600, 1000))
        m["speed_dps"] = float(rng.uniform(5, 40))
    elif scenario == "reversed":               # wired/assembled backwards
        direction = "decreasing"
    elif scenario == "out_of_range":           # worn / limited travel
        m["range_deg"] = float(rng.uniform(60, 90))
    elif scenario == "slow":                   # weak motor / high friction
        m["speed_dps"] = float(rng.uniform(70, 150))
    elif scenario == "offcenter":              # pot/horn off -> center wrong
        m["center_off_deg"] = float(rng.uniform(16, 28))
    else:
        raise ValueError(f"unknown functional scenario: {scenario!r}")

    # Derived raw readings for traceability (consistent with the above).
    center = 90.0 + (m["center_off_deg"] if rng.random() < 0.5 else -m["center_off_deg"])
    half = m["range_deg"] / 2.0
    m["angle_center"] = float(center)
    m["angle_min"] = float(center - half if direction == "increasing" else center + half)
    m["angle_max"] = float(center + half if direction == "increasing" else center - half)
    m["sweep_ms"] = float(m["range_deg"] / m["speed_dps"] * 1000.0) if m["speed_dps"] > 1 else 9999.0
    m["direction"] = direction
    return m


class SimInstrument(Instrument):
    def __init__(self, cfg: DutConfig, scenario: str = "good", seed: int | None = None):
        self.cfg = cfg
        self.scenario = scenario
        self.rng = np.random.default_rng(seed)

    def identify(self) -> protocol.IdInfo:
        return protocol.IdInfo(name="SERVOTEST-CAM-SIM", version="2.0")

    def run(self) -> MeasResult:
        raw = build_meas(self.cfg, self.scenario, self.rng)
        # Emit and re-parse the real wire format (round-trips protocol.py).
        meas: dict = {}
        for key, value in raw.items():
            line = protocol.build_meas(key, value)
            k, v = protocol.parse_meas(line)
            meas[k] = v
        elapsed = int(self.cfg.settle_ms * 3 + 80 + self.rng.normal(0, 15))
        return MeasResult(meas=meas, elapsed_ms=max(1, elapsed))
