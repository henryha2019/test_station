"""Gage-R&R-style repeatability: prove the TESTER isn't the source of variation.

Run one known-good unit many times: the verdict must be identical every time.
Report the spread of the analog-ish readings (vision confidence, latency) so you
can show the decision is stable even though the raw readings jitter. Optionally
run a known-bad unit to confirm zero escapes.

    python -m analysis.repeatability --runs 30
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from host.camera import SimCamera
from host.config import DEFAULT_CONFIG, load_config
from host.inspection import make_inspector
from host.instrument import SimInstrument
from host.orchestrator import Station


def _run(cfg, scenario, dut_class, runs, seed):
    station = Station(
        cfg,
        SimInstrument(cfg, scenario=scenario, seed=seed),
        SimCamera(cfg, dut_class=dut_class, seed=seed),
        make_inspector(cfg),
    )
    recs = [station.run_unit(f"RPT{i:03d}") for i in range(runs)]
    return recs


def analyze(cfg, runs=30, seed=123, out="out"):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)

    good = _run(cfg, "good", "OK", runs, seed)
    verdicts = {r.final_result for r in good}
    conf = np.array([r.vision_conf for r in good])
    infer = np.array([r.infer_ms for r in good])
    stable = verdicts == {"PASS"}

    # Use an unambiguously out-of-spec unit for the escape check (a gage study
    # uses clearly good / clearly bad parts, not borderline ones).
    bad_class = "horn_missing"
    bad = _run(cfg, "good", bad_class, runs, seed + 1)
    escapes = sum(1 for r in bad if r.final_result == "PASS")

    print(f"Repeatability — {runs} runs of one known-good unit")
    print(f"  verdict stability : {'PASS x%d (STABLE)' % runs if stable else 'UNSTABLE %s' % verdicts}")
    print(f"  vision confidence : mean {conf.mean():.3f}  sd {conf.std():.4f}  "
          f"min {conf.min():.3f}  max {conf.max():.3f}")
    print(f"  inference latency : mean {infer.mean():.2f} ms  sd {infer.std():.2f} ms")
    print(f"\nKnown-bad unit ({bad_class}) x{runs}: "
          f"{runs - escapes}/{runs} caught, {escapes} escapes")

    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.hist(conf, bins=12, color="#1b8a3a", alpha=0.85)
    ax.axvline(cfg.vision.ok_threshold, color="#b3261e", ls="--",
               label=f"ok_threshold {cfg.vision.ok_threshold:.2f}")
    ax.set_xlabel("P(OK) on a known-good unit"); ax.set_ylabel("runs")
    ax.set_title(f"Reading spread (verdict {runs}x stable={stable})")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out / "repeatability.png", dpi=120); plt.close(fig)
    print(f"Artifact: {out}/repeatability.png")

    return {"runs": runs, "verdict_stable": bool(stable),
            "conf_mean": float(conf.mean()), "conf_sd": float(conf.std()),
            "infer_mean_ms": float(infer.mean()), "escapes": int(escapes)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Gage-R&R-style repeatability check")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--runs", type=int, default=30)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--out", default="out")
    args = p.parse_args(argv)
    analyze(load_config(args.config), args.runs, args.seed, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
