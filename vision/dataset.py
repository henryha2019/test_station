"""Build a reproducible train/test manifest from vision/data/<class>/*.

Stratified hold-out split (same fraction per class) with a fixed seed, so the
test set is never touched by training and the manifest regenerates identically.

    python -m vision.dataset --test-frac 0.2
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def scan(data_dir: Path) -> dict[str, list[Path]]:
    classes = {}
    for d in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        files = sorted(f for f in d.iterdir() if f.suffix.lower() in IMG_EXTS)
        if files:
            classes[d.name] = files
    return classes


def build_manifest(data_dir="vision/data", out="vision/manifest.csv",
                   test_frac=0.2, seed=11) -> dict:
    data_dir = Path(data_dir)
    classes = scan(data_dir)
    if not classes:
        raise SystemExit(f"no images under {data_dir}/ — run vision.make_synthetic first")

    rng = np.random.default_rng(seed)
    rows = []
    counts = {}
    for label, files in classes.items():
        idx = np.arange(len(files))
        rng.shuffle(idx)
        n_test = max(1, int(round(len(files) * test_frac)))
        test_set = set(idx[:n_test].tolist())
        n_tr = n_te = 0
        for i, f in enumerate(files):
            split = "test" if i in test_set else "train"
            rows.append((f.as_posix(), label, split))
            if split == "test":
                n_te += 1
            else:
                n_tr += 1
        counts[label] = {"train": n_tr, "test": n_te}

    out = Path(out)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "label", "split"])
        w.writerows(rows)

    print(f"manifest -> {out}  ({len(rows)} images)")
    for label, c in counts.items():
        print(f"  {label:<18} train {c['train']:>4}  test {c['test']:>4}")
    return {"path": str(out), "counts": counts, "n": len(rows)}


def load_manifest(path="vision/manifest.csv", split=None) -> list[tuple[str, str]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if split is None or r["split"] == split:
                rows.append((r["path"], r["label"]))
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build dataset manifest with train/test split")
    p.add_argument("--data", default="vision/data")
    p.add_argument("--out", default="vision/manifest.csv")
    p.add_argument("--test-frac", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args(argv)
    build_manifest(args.data, args.out, args.test_frac, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
