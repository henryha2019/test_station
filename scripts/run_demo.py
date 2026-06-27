"""End-to-end simulated demo — the whole station, no hardware.

Runs the full pipeline and drops every portfolio artifact into out/:
  1. synthetic dataset + manifest          (Phase 4)
  2. vision evaluation: confusion matrix + operating point   (Phase 5)
  3. a station session (random units + 3 scripted illustrative units) -> logs/  (Phase 2/6)
  4. yield / Pareto / cycle-time analysis   (Phase 8)
  5. Gage-R&R repeatability                 (Phase 8)

    python scripts/run_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from host.app import _inject  # noqa: E402
from host.camera import SimCamera  # noqa: E402
from host.config import load_config  # noqa: E402
from host.inspection import make_inspector  # noqa: E402
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

    banner("1/5  Synthetic dataset + manifest")
    from vision.make_synthetic import main as gen
    gen(["--per-class", "150"])
    from vision.dataset import build_manifest
    build_manifest()

    banner("2/5  Vision evaluation (confusion matrix + operating point)")
    from vision.evaluate import evaluate
    evaluate(cfg, "vision/manifest.csv", model_path=None, out=str(ROOT / "out"))

    banner("3/5  Station session")
    rng = np.random.default_rng(42)
    log = TraceLog(log_path)
    station = Station(cfg, SimInstrument(cfg, seed=42), SimCamera(cfg, seed=42),
                      make_inspector(cfg), log=log)
    for i in range(1, 41):                       # 40 random units
        station.instrument.scenario, station.camera.dut_class = _inject(rng)
        station.run_unit(f"SN{i:04d}")
    # Three scripted, illustrative units (the demo's punchline).
    scripted = [("good", "OK"), ("good", "horn_missing"), ("stalled", "OK")]
    for k, (sc, dc) in enumerate(scripted, start=41):
        station.instrument.scenario, station.camera.dut_class = sc, dc
        r = station.run_unit(f"SN{k:04d}")
        print(f"  {r.serial}: func={r.functional_result}({r.fail_param}) "
              f"vision={r.vision_result}({r.vision_class}) -> {r.final_result} [{r.fail_reason}]")
    log.close()
    print(f"FPY this session: {station.fpy:.1f}%  ({station.passed}/{station.tested})")

    banner("4/5  Yield / Pareto / cycle-time")
    from analysis.metrics import analyze as yield_analyze
    yield_analyze(str(log_path), str(ROOT / "out"))

    banner("5/5  Gage-R&R repeatability")
    from analysis.repeatability import analyze as rpt
    rpt(cfg, runs=30, out=str(ROOT / "out"))

    banner("DONE")
    print("Artifacts in out/:  confusion_matrix.png, operating_point.png,")
    print("                    fpy_trend.png, pareto.png, cycle_time.png, repeatability.png")
    print("Trace log:          logs/log.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
