"""Generate a labeled synthetic dataset (stand-in for shroud captures).

Labels are baked into the directory path (vision/data/<class>/...), so no manual
relabeling is ever needed. Replace with vision/capture.py output for production;
the layout is identical.

    python -m vision.make_synthetic --per-class 300
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from vision.synthimg import CLASSES, render


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate synthetic DUT dataset")
    p.add_argument("--per-class", type=int, default=300)
    p.add_argument("--out", default="vision/data")
    p.add_argument("--size", type=int, nargs=2, default=[96, 96], metavar=("H", "W"))
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    total = 0
    for cls in CLASSES:
        d = out / cls
        d.mkdir(parents=True, exist_ok=True)
        for i in range(args.per_class):
            arr = render(cls, tuple(args.size), rng)
            Image.fromarray(arr, "RGB").save(d / f"{cls}_{i:04d}.png")
            total += 1
        print(f"  {cls:<18} {args.per_class} images -> {d}")
    print(f"Done: {total} images under {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
