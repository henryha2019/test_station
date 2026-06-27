"""Servo-tester serial wire protocol (parse + build).

Kept separate from transport so the real serial instrument and the simulator
share one source of truth for the wire format, and so it can be unit-tested
without any port.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---- Host -> Uno commands -------------------------------------------------
CMD_ID = "ID?"
CMD_PING = "PING"
CMD_RUN = "RUN"


@dataclass(frozen=True)
class IdInfo:
    name: str
    version: str


def parse_id(line: str) -> IdInfo:
    """Parse 'ID,SERVOTEST-UNO,2.0'."""
    parts = line.strip().split(",")
    if len(parts) < 3 or parts[0] != "ID":
        raise ValueError(f"bad ID line: {line!r}")
    return IdInfo(name=parts[1], version=parts[2])


def parse_meas(line: str) -> tuple[str, object]:
    """Parse 'MEAS,<key>,<value>' -> (key, value).

    Numeric values come back as float; non-numeric (e.g. direction) stay str.
    """
    parts = line.strip().split(",")
    if len(parts) != 3 or parts[0] != "MEAS":
        raise ValueError(f"bad MEAS line: {line!r}")
    key, raw = parts[1], parts[2]
    try:
        return key, float(raw)
    except ValueError:
        return key, raw


def parse_done(line: str) -> int:
    """Parse 'DONE,<elapsed_ms>' -> elapsed_ms."""
    parts = line.strip().split(",")
    if len(parts) != 2 or parts[0] != "DONE":
        raise ValueError(f"bad DONE line: {line!r}")
    return int(float(parts[1]))


def build_meas(key: str, value) -> str:
    if isinstance(value, float):
        return f"MEAS,{key},{value:.3f}"
    return f"MEAS,{key},{value}"


def build_done(elapsed_ms: int) -> str:
    return f"DONE,{elapsed_ms}"
