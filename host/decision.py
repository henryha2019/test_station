"""The dual-criteria verdict: PASS = functional AND vision.

This is the whole point of v2.0 — the functional test catches a servo that won't
travel, stalls, draws bad current, or runs backwards; vision catches assembly /
appearance defects (missing horn, cracked case, foreign object). A unit ships
only if both agree. The log records WHICH criterion failed so the Pareto is real.
"""
from __future__ import annotations

from dataclasses import dataclass

from .functional import FunctionalResult
from .inspection import VisionResult


@dataclass
class Verdict:
    final_pass: bool
    functional_pass: bool
    vision_pass: bool
    reason: str          # "-", "FUNCTIONAL", "VISION", or "FUNCTIONAL+VISION"


def decide(functional: FunctionalResult, vision: VisionResult) -> Verdict:
    f, v = functional.passed, vision.passed
    if f and v:
        reason = "-"
    elif not f and not v:
        reason = "FUNCTIONAL+VISION"
    elif not f:
        reason = "FUNCTIONAL"
    else:
        reason = "VISION"
    return Verdict(final_pass=f and v, functional_pass=f, vision_pass=v, reason=reason)
