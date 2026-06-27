"""Yield + failure-mode + cycle-time analysis from logs/log.csv.

Produces the three artifacts that make a tester credible:
  * FPY trend     — first-pass yield over the session
  * Pareto        — which failure mode dominates (where to spend engineering)
  * cycle time    — mean and worst-case throughput

    python -m analysis.metrics
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def read_log(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"{path} not found — run the station first (host.app --log {path})")
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def failure_mode(row: dict) -> str:
    reason = row["fail_reason"]
    if reason == "FUNCTIONAL":
        return f"FUNC:{row['fail_param']}"
    if reason == "VISION":
        return f"VIS:{row['vision_class']}"
    if reason == "FUNCTIONAL+VISION":
        return "FUNC+VIS"
    return "-"


def analyze(log="logs/log.csv", out="out") -> dict:
    rows = read_log(log)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    n = len(rows)
    passes = [r["final_result"] == "PASS" for r in rows]
    fpy = 100.0 * sum(passes) / n if n else 0.0

    # FPY trend (cumulative).
    cum = np.cumsum(passes) / np.arange(1, n + 1) * 100.0
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(range(1, n + 1), cum, color="#2d6cdf")
    ax.axhline(fpy, ls="--", color="#888", lw=1, label=f"final {fpy:.1f}%")
    ax.set_xlabel("unit #"); ax.set_ylabel("cumulative FPY (%)")
    ax.set_ylim(0, 105); ax.set_title("First-pass yield"); ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "fpy_trend.png", dpi=120); plt.close(fig)

    # Pareto of failure modes.
    modes = Counter(failure_mode(r) for r in rows if r["final_result"] == "FAIL")
    pareto = modes.most_common()
    if pareto:
        labels = [m for m, _ in pareto]
        counts = np.array([c for _, c in pareto])
        cumpct = np.cumsum(counts) / counts.sum() * 100
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(range(len(labels)), counts, color="#b3261e")
        ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("failures")
        ax2 = ax.twinx()
        ax2.plot(range(len(labels)), cumpct, "-o", color="#333", ms=4)
        ax2.set_ylim(0, 105); ax2.set_ylabel("cumulative %")
        ax.set_title("Failure-mode Pareto")
        fig.tight_layout(); fig.savefig(out / "pareto.png", dpi=120); plt.close(fig)

    # Cycle time.
    cyc = np.array([float(r["cycle_ms"]) for r in rows if r.get("cycle_ms")])
    cyc_stats = {}
    if cyc.size:
        cyc_stats = {"mean_ms": float(cyc.mean()),
                     "p95_ms": float(np.percentile(cyc, 95)),
                     "max_ms": float(cyc.max())}
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.hist(cyc, bins=min(20, max(5, cyc.size // 2)), color="#2d6cdf", alpha=0.85)
        ax.axvline(cyc_stats["mean_ms"], color="#1b8a3a", lw=1.5,
                   label=f"mean {cyc_stats['mean_ms']:.1f} ms")
        ax.axvline(cyc_stats["p95_ms"], color="#b3261e", lw=1.5, ls="--",
                   label=f"p95 {cyc_stats['p95_ms']:.1f} ms")
        ax.set_xlabel("cycle time (ms)"); ax.set_ylabel("units")
        ax.set_title("Cycle time"); ax.legend(fontsize=8)
        fig.tight_layout(); fig.savefig(out / "cycle_time.png", dpi=120); plt.close(fig)

    summary = {"units": n, "fpy_pct": round(fpy, 2),
               "failure_modes": dict(pareto), "cycle_ms": cyc_stats}

    print(f"Units {n}   FPY {fpy:.1f}%")
    if pareto:
        print("Failure Pareto:")
        for m, c in pareto:
            print(f"  {m:<22} {c}")
    if cyc_stats:
        print(f"Cycle time: mean {cyc_stats['mean_ms']:.1f} ms, "
              f"p95 {cyc_stats['p95_ms']:.1f} ms, max {cyc_stats['max_ms']:.1f} ms")
    print(f"Artifacts: {out}/fpy_trend.png, {out}/pareto.png, {out}/cycle_time.png")
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Yield / Pareto / cycle-time analysis")
    p.add_argument("--log", default="logs/log.csv")
    p.add_argument("--out", default="out")
    args = p.parse_args(argv)
    analyze(args.log, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
