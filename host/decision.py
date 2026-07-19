"""The station verdict.

This tester is single-criterion: PASS = the servo's functional response is within
spec. (Visual inspection has been split out into its own project; the vision
pipeline is parked under `vision/`.) The host owns this decision.
"""
from __future__ import annotations

from dataclasses import dataclass

from .functional import FunctionalResult


@dataclass
class Verdict:
    final_pass: bool
    functional_pass: bool
    reason: str          # "-" or "FUNCTIONAL"


def decide(functional: FunctionalResult) -> Verdict:
    f = functional.passed
    return Verdict(final_pass=f, functional_pass=f, reason="-" if f else "FUNCTIONAL")
