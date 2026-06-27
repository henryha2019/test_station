"""Functional verdict: check the servo's measured response against limit windows.

The instrument commands the servo to min / center / max and reports raw readings
(actual angle from the AS5600, current from the INA219, sweep timing). The host
(not the instrument) compares each reading to the recipe's spec window, so the
firmware stays product-agnostic.

A measured value out of its window is a parametric failure naming the parameter,
the value, and the bound it broke — which is what makes the Pareto and Cpk real.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import DutConfig


@dataclass
class Failure:
    param: str
    value: object
    kind: str          # "low" / "high" / "mismatch"
    bound: str         # human-readable limit, e.g. "[100,140]"

    def __str__(self) -> str:
        v = f"{self.value:g}" if isinstance(self.value, (int, float)) else self.value
        return f"{self.param}={v}{('<' if self.kind=='low' else '>') if self.kind in ('low','high') else '!='}{self.bound}"


@dataclass
class FunctionalResult:
    passed: bool
    failures: list[Failure]
    meas: dict
    elapsed_ms: int = 0

    @property
    def fail_param(self) -> str:
        return self.failures[0].param if self.failures else "-"

    def summary(self) -> str:
        if self.passed:
            return "PASS"
        return "FAIL " + ", ".join(str(f) for f in self.failures)


def evaluate(meas: dict, cfg: DutConfig, elapsed_ms: int = 0) -> FunctionalResult:
    failures: list[Failure] = []
    for key, limit in cfg.limits.items():
        if key not in meas:
            failures.append(Failure(key, "missing", "mismatch", limit.describe()))
            continue
        ok, kind = limit.check(meas[key])
        if not ok:
            failures.append(Failure(key, meas[key], kind, limit.describe()))
    return FunctionalResult(
        passed=len(failures) == 0,
        failures=failures,
        meas=meas,
        elapsed_ms=elapsed_ms,
    )
