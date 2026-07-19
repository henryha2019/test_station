"""Gage-R&R-style repeatability: prove the TESTER isn't the source of variation.

Run one known-good servo many times: the verdict must be identical every time,
while the raw analog reading (measured travel) jitters. Reporting that spread
against the spec window shows the decision is robust to reading noise. Then run a
known-bad servo to confirm zero escapes.

    python -m analysis.repeatability --runs 30
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from host.config import DEFAULT_CONFIG, load_config
from host.instrument import SimInstrument
from host.orchestrator import Station


def _run(cfg, scenario, runs, seed):
    station = Station(cfg, SimInstrument(cfg, scenario=scenario, seed=seed))
    return [station.run_unit(f"RPT{i:03d}") for i in range(runs)]


def analyze(cfg, runs=30, seed=123, out="out"):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)

    good = _run(cfg, "good", runs, seed)
    verdicts = {r.final_result for r in good}
    rng_deg = np.array([r.range_deg for r in good], dtype=float)
    move = np.array([r.move_mA for r in good], dtype=float)
    stable = verdicts == {"PASS"}

    # Unambiguously out-of-spec servo for the escape check.
    bad_scenario = "stalled"
    bad = _run(cfg, bad_scenario, runs, seed + 1)
    escapes = sum(1 for r in bad if r.final_result == "PASS")

    lim = cfg.limits["range_deg"]
    print(f"Repeatability — {runs} runs of one known-good servo")
    print(f"  verdict stability : {'PASS x%d (STABLE)' % runs if stable else 'UNSTABLE %s' % verdicts}")
    print(f"  range_deg reading : mean {rng_deg.mean():.2f}  sd {rng_deg.std():.3f}  "
          f"min {rng_deg.min():.2f}  max {rng_deg.max():.2f}  (spec {lim.describe()})")
    print(f"  move_mA reading   : mean {move.mean():.1f}  sd {move.std():.2f} mA")
    print(f"\nKnown-bad servo ({bad_scenario}) x{runs}: "
          f"{runs - escapes}/{runs} caught, {escapes} escapes")

    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.hist(rng_deg, bins=12, color="#1b8a3a", alpha=0.85)
    for b in (lim.min, lim.max):
        if b is not None:
            ax.axvline(b, color="#b3261e", ls="--", label=f"spec {lim.describe()}")
    ax.set_xlabel("measured range_deg on a known-good servo"); ax.set_ylabel("runs")
    ax.set_title(f"Reading spread (verdict {runs}x stable={stable})")
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend(handles[:1], labels[:1], fontsize=8)
    fig.tight_layout(); fig.savefig(out / "repeatability.png", dpi=120); plt.close(fig)
    print(f"Artifact: {out}/repeatability.png")

    return {"runs": runs, "verdict_stable": bool(stable),
            "range_mean": float(rng_deg.mean()), "range_sd": float(rng_deg.std()),
            "escapes": int(escapes)}


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
