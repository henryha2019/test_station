"""End-to-end simulated demo — the functional servo station, no hardware.

Drops the portfolio artifacts into out/:
  1. a station session (random units + scripted illustrative faults) -> logs/
  2. yield / Pareto / cycle-time analysis
  3. Gage-R&R repeatability

    python scripts/run_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from host.app import _inject  # noqa: E402
from host.config import load_config  # noqa: E402
from host.instrument import SimInstrument  # noqa: E402
from host.orchestrator import Station  # noqa: E402
from host.tracelog import TraceLog  # noqa: E402


def banner(t):
    print("\n" + "=" * 64 + f"\n {t}\n" + "=" * 64)


def main() -> int:
    cfg = load_config()
    log_path = ROOT / "logs" / "log.csv"
    if log_path.exists():
        log_path.unlink()

    banner("1/3  Station session")
    rng = np.random.default_rng(42)
    log = TraceLog(log_path)
    station = Station(cfg, SimInstrument(cfg, seed=42), log=log)
    for i in range(1, 41):                       # 40 random units
        station.instrument.scenario = _inject(rng)
        station.run_unit(f"SN{i:04d}")
    # Scripted, illustrative faults (the demo's punchline).
    scripted = ["good", "stalled", "out_of_range", "reversed"]
    for k, sc in enumerate(scripted, start=41):
        station.instrument.scenario = sc
        r = station.run_unit(f"SN{k:04d}")
        print(f"  {r.serial}: {sc:<12} -> func={r.functional_result} "
              f"range={r.range_deg}° -> {r.final_result} [{r.fail_reason}:{r.fail_param}]")
    log.close()
    print(f"FPY this session: {station.fpy:.1f}%  ({station.passed}/{station.tested})")

    banner("2/3  Yield / Pareto / cycle-time")
    from analysis.metrics import analyze as yield_analyze
    yield_analyze(str(log_path), str(ROOT / "out"))

    banner("3/3  Gage-R&R repeatability")
    from analysis.repeatability import analyze as rpt
    rpt(cfg, runs=30, out=str(ROOT / "out"))

    banner("DONE")
    print("Artifacts in out/:  fpy_trend.png, pareto.png, cycle_time.png, repeatability.png")
    print("Trace log:          logs/log.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
